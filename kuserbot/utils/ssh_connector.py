"""
utils/ssh_connector.py
======================
Async-friendly SSH / SFTP manager for the Aiogram v3 Telegram Master Bot.

All blocking Paramiko calls are off-loaded to a worker thread via
``asyncio.to_thread`` so the Aiogram event-loop never freezes.

Usage
-----
    async with SSHManager("host", "user", "pass") as ssh:
        if not await ssh.connect():
            return
        await ssh.deploy_worker_bot("./worker_bot")
        await ssh.install_requirements()
        pid = await ssh.start_userbot(session_string, api_id, api_hash)
"""

from __future__ import annotations

import asyncio
import logging
import os
import shlex
import socket
import stat
import threading
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import paramiko

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------
class SSHConnectionError(Exception):
    """Generic SSH connection-level failure."""


class SSHNotConnectedError(RuntimeError):
    """Raised when an operation runs before ``connect()`` or after ``close()``."""


class SFTPError(Exception):
    """Raised for SFTP-level failures."""


# ---------------------------------------------------------------------------
# Command result container
# ---------------------------------------------------------------------------
@dataclass(slots=True)
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            f"CommandResult(exit={self.exit_code}, "
            f"stdout={len(self.stdout)}B, stderr={len(self.stderr)}B)"
        )


# ---------------------------------------------------------------------------
# Upload filters
# ---------------------------------------------------------------------------
_IGNORED_DIR_NAMES: frozenset[str] = frozenset(
    {"__pycache__", ".git", ".idea", ".vscode", ".pytest_cache", ".mypy_cache"}
)
_IGNORED_FILE_SUFFIXES: frozenset[str] = frozenset({".pyc", ".pyo", ".json"})
_IGNORED_FILE_NAMES: frozenset[str] = frozenset({".DS_Store", "Thumbs.db"})


def _should_upload_file(file_path: Path) -> bool:
    """Decide whether a local file should be uploaded."""
    if file_path.name in _IGNORED_FILE_NAMES:
        return False
    if file_path.suffix in _IGNORED_FILE_SUFFIXES:
        return False
    return True


def _should_walk_into(dir_path: Path) -> bool:
    return dir_path.name not in _IGNORED_DIR_NAMES


# ---------------------------------------------------------------------------
# SSHManager
# ---------------------------------------------------------------------------
class SSHManager:
    """
    High-level async wrapper around :class:`paramiko.SSHClient`.

    The same instance must NOT be shared between concurrent asyncio tasks
    if those tasks issue commands in parallel — Paramiko itself is not
    thread-safe, and although this class serialises every blocking call
    through a ``threading.Lock``, ordering between coroutines is still
    FIFO. For parallel work, instantiate one ``SSHManager`` per task.
    """

    DEFAULT_CONNECT_TIMEOUT: float = 15.0
    DEFAULT_CMD_TIMEOUT: float = 120.0
    PIP_TIMEOUT: float = 600.0

    # ------------------------------------------------------------------ #
    # Construction                                                       #
    # ------------------------------------------------------------------ #
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        port: int = 22,
        connect_timeout: float = DEFAULT_CONNECT_TIMEOUT,
    ) -> None:
        self.host: str = host
        self.username: str = username
        self.password: str = password
        self.port: int = port
        self.connect_timeout: float = connect_timeout

        self._client: Optional[paramiko.SSHClient] = None
        self._sftp: Optional[paramiko.SFTPClient] = None

        # Paramiko's SSHClient is NOT thread-safe. Even though from the
        # asyncio side we are single-coroutine, ``asyncio.to_thread``
        # dispatches to a shared ThreadPoolExecutor — two concurrently
        # awaited methods could land on different worker threads and
        # corrupt the session. We serialise every blocking call.
        self._lock: threading.Lock = threading.Lock()

    # ------------------------------------------------------------------ #
    # Async-context-manager sugar                                        #
    # ------------------------------------------------------------------ #
    async def __aenter__(self) -> "SSHManager":
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    # ------------------------------------------------------------------ #
    # Internal helpers                                                   #
    # ------------------------------------------------------------------ #
    def _ensure_client(self) -> paramiko.SSHClient:
        if self._client is None:
            raise SSHNotConnectedError(
                "SSH session is not open. Call connect() first / after close()."
            )
        return self._client

    async def _run_in_thread(self, fn, *args, **kwargs) -> Any:
        """Run *fn* on a worker thread while holding the instance lock."""
        def _guarded():
            with self._lock:
                return fn(*args, **kwargs)
        return await asyncio.to_thread(_guarded)

    # ------------------------------------------------------------------ #
    # 1. connect                                                         #
    # ------------------------------------------------------------------ #
    async def connect(self) -> bool:
        """
        Establish the SSH connection.

        Returns ``True`` on success, ``False`` on auth / SSH / socket
        errors (which are logged but not re-raised, per spec).
        """
        logger.info("Connecting to %s@%s:%s ...", self.username, self.host, self.port)

        def _blocking() -> bool:
            client = paramiko.SSHClient()
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                client.connect(
                    hostname=self.host,
                    port=self.port,
                    username=self.username,
                    password=self.password,
                    timeout=self.connect_timeout,
                    banner_timeout=self.connect_timeout,
                    auth_timeout=self.connect_timeout,
                    look_for_keys=False,
                    allow_agent=False,
                )
            except paramiko.AuthenticationException as e:
                logger.error("SSH auth failed for %s@%s: %s", self.username, self.host, e)
                return False
            except paramiko.SSHException as e:
                logger.error("SSH protocol error on %s: %s", self.host, e)
                return False
            except (socket.error, OSError) as e:
                logger.error("Network error connecting to %s: %s", self.host, e)
                return False
            except Exception as e:  # pragma: no cover - defensive
                logger.exception("Unexpected error connecting to %s: %s", self.host, e)
                return False

            self._client = client
            logger.info("SSH connection to %s established.", self.host)
            return True

        return await self._run_in_thread(_blocking)

    # ------------------------------------------------------------------ #
    # SFTP internals                                                     #
    # ------------------------------------------------------------------ #
    def _get_sftp_blocking(self) -> paramiko.SFTPClient:
        client = self._ensure_client()
        if self._sftp is None:
            transport = client.get_transport()
            if transport is None or not transport.is_active():
                raise SSHNotConnectedError("Underlying SSH transport is not active.")
            sftp = paramiko.SFTPClient.from_transport(transport)
            if sftp is None:
                raise SFTPError("Could not open SFTP channel over the SSH transport.")
            self._sftp = sftp
        return self._sftp

    def _mkdir_p_blocking(self, sftp: paramiko.SFTPClient, remote_path: str) -> None:
        """Recursively create *remote_path* (``mkdir -p`` semantics)."""
        if remote_path in ("", ".", "/"):
            return
        try:
            st = sftp.stat(remote_path)
            if stat.S_ISDIR(st.st_mode):
                return
            raise SFTPError(f"Remote path exists but is not a directory: {remote_path}")
        except FileNotFoundError:
            parent = os.path.dirname(remote_path.rstrip("/"))
            self._mkdir_p_blocking(sftp, parent)
            try:
                sftp.mkdir(remote_path)
            except IOError:
                # Race: someone else created it between stat and mkdir.
                with suppress(FileNotFoundError):
                    if stat.S_ISDIR(sftp.stat(remote_path).st_mode):
                        return
                raise

    def _upload_file_blocking(
        self,
        sftp: paramiko.SFTPClient,
        local_path: Path,
        remote_path: str,
    ) -> None:
        logger.debug("Uploading %s -> %s", local_path, remote_path)
        sftp.put(str(local_path), remote_path)
        with suppress(IOError):
            sftp.chmod(remote_path, 0o644)

    # ------------------------------------------------------------------ #
    # 5. deploy_worker_bot                                               #
    # ------------------------------------------------------------------ #
    async def deploy_worker_bot(self, worker_bot_dir: str) -> None:
        """
        Recursively upload the local *worker_bot_dir* to ``worker_bot/``
        on the remote server.

        * Creates ``worker_bot/`` and ``worker_bot/modules/`` if missing.
        * Walks one directory level deep (enough for a typical worker bot
          layout). ``__pycache__``, ``.git``, ``.json`` data files and
          ``.pyc``/``.pyo`` files are skipped.
        """
        local_root = Path(worker_bot_dir).resolve()
        if not local_root.is_dir():
            raise FileNotFoundError(f"Local worker_bot directory not found: {local_root}")

        remote_root = "worker_bot"
        logger.info(
            "Deploying %s -> %s@%s:%s",
            local_root, self.username, self.host, remote_root,
        )

        def _blocking() -> None:
            sftp = self._get_sftp_blocking()
            self._mkdir_p_blocking(sftp, remote_root)
            self._mkdir_p_blocking(sftp, f"{remote_root}/modules")

            uploaded = 0
            skipped = 0

            for entry in sorted(local_root.iterdir()):
                if entry.is_dir():
                    if not _should_walk_into(entry):
                        continue
                    remote_sub = f"{remote_root}/{entry.name}"
                    self._mkdir_p_blocking(sftp, remote_sub)
                    for sub_entry in sorted(entry.iterdir()):
                        if sub_entry.is_dir():
                            # Skip deeper nesting; worker_bot is flat.
                            continue
                        if not _should_upload_file(sub_entry):
                            skipped += 1
                            continue
                        self._upload_file_blocking(
                            sftp, sub_entry, f"{remote_sub}/{sub_entry.name}"
                        )
                        uploaded += 1
                else:
                    if not _should_upload_file(entry):
                        skipped += 1
                        continue
                    self._upload_file_blocking(
                        sftp, entry, f"{remote_root}/{entry.name}"
                    )
                    uploaded += 1

            logger.info(
                "Deployment of %s complete: %d uploaded, %d skipped.",
                local_root.name, uploaded, skipped,
            )

        await self._run_in_thread(_blocking)

    # ------------------------------------------------------------------ #
    # 6. install_requirements                                            #
    # ------------------------------------------------------------------ #
    async def install_requirements(self) -> CommandResult:
        """
        Install Telethon and (optionally) ``worker_bot/requirements.txt``
        on the remote host via ``pip``.
        """
        cmd = (
            "pip install --quiet --no-input telethon && "
            "if [ -f worker_bot/requirements.txt ]; then "
            "  pip install --quiet --no-input -r worker_bot/requirements.txt; "
            "fi"
        )
        logger.info("Installing remote requirements on %s ...", self.host)
        return await self.execute_command(cmd, timeout=self.PIP_TIMEOUT)

    # ------------------------------------------------------------------ #
    # 7. start_userbot                                                   #
    # ------------------------------------------------------------------ #
    async def start_userbot(
        self,
        session_string: str,
        api_id: int,
        api_hash: str,
    ) -> Optional[int]:
        """
        Start the userbot in the background with ``nohup``.

        Returns the PID of the spawned process if it can be reliably
        captured, ``None`` otherwise.
        """
        # shlex.quote defends against shell injection through session_string.
        cmd = (
            "cd worker_bot && "
            f"export API_ID={shlex.quote(str(api_id))} "
            f"API_HASH={shlex.quote(api_hash)} "
            f"SESSION_STRING={shlex.quote(session_string)} && "
            "nohup python -m worker_bot.userbot > userbot.log 2>&1 & "
            "echo $!"
        )
        logger.info("Launching userbot on %s ...", self.host)
        result = await self.execute_command(cmd, timeout=30.0)
        if not result.ok:
            logger.error(
                "start_userbot failed (exit=%s): %s",
                result.exit_code, result.stderr.strip(),
            )
            return None

        pid_str = result.stdout.strip().splitlines()[-1] if result.stdout.strip() else ""
        if pid_str.isdigit():
            pid = int(pid_str)
            logger.info("Userbot started on %s with PID %d.", self.host, pid)
            return pid

        logger.warning("Could not parse PID from stdout: %r", result.stdout)
        return None

    # ------------------------------------------------------------------ #
    # 8. execute_command                                                 #
    # ------------------------------------------------------------------ #
    async def execute_command(
        self,
        command: str,
        timeout: float = DEFAULT_CMD_TIMEOUT,
    ) -> CommandResult:
        """Run *command* on the remote host and return its output."""
        client = self._ensure_client()

        def _blocking() -> CommandResult:
            stdin, stdout, stderr = client.exec_command(command, timeout=timeout)
            stdin.close()
            try:
                out_bytes = stdout.read()
                err_bytes = stderr.read()
                exit_code = stdout.channel.recv_exit_status()
            except socket.timeout as e:
                raise TimeoutError(
                    f"Command timed out after {timeout}s: {command[:120]!r}"
                ) from e

            out = out_bytes.decode("utf-8", errors="replace")
            err = err_bytes.decode("utf-8", errors="replace")
            logger.debug("[cmd] %s -> exit=%s", command[:120], exit_code)
            return CommandResult(exit_code=exit_code, stdout=out, stderr=err)

        return await self._run_in_thread(_blocking)

    # ------------------------------------------------------------------ #
    # 9. close                                                           #
    # ------------------------------------------------------------------ #
    async def close(self) -> None:
        """Close SFTP and SSH connections safely (never raises)."""
        def _blocking() -> None:
            if self._sftp is not None:
                with suppress(Exception):
                    self._sftp.close()
                self._sftp = None
            if self._client is not None:
                with suppress(Exception):
                    self._client.close()
                self._client = None
            logger.info("SSH connection to %s closed.", self.host)

        await self._run_in_thread(_blocking)

    # ------------------------------------------------------------------ #
    # Bonus utilities (handy for master-bot admin commands)              #
    # ------------------------------------------------------------------ #
    async def is_process_running(self, pid: int) -> bool:
        """Check whether a remote PID is alive (``kill -0``)."""
        result = await self.execute_command(f"kill -0 {int(pid)} 2>/dev/null && echo OK")
        return result.ok and "OK" in result.stdout

    async def kill_userbot(self) -> CommandResult:
        """Best-effort termination of any running userbot process."""
        return await self.execute_command(
            "pkill -f 'python -m worker_bot.userbot' || true"
        )

    async def tail_log(self, lines: int = 50) -> str:
        """Return the last *lines* of ``worker_bot/userbot.log``."""
        result = await self.execute_command(
            f"tail -n {int(lines)} worker_bot/userbot.log 2>/dev/null"
        )
        return result.stdout


__all__ = [
    "SSHManager",
    "CommandResult",
    "SSHConnectionError",
    "SSHNotConnectedError",
    "SFTPError",
]