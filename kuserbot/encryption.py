"""
encryption.py

Provides symmetric AES encryption utilities for the Telegram Bot using
the ``cryptography.fernet`` library (AES-128-CBC with HMAC-SHA256
authentication).

The encryption key is loaded from the ``ENCRYPTION_KEY`` environment
variable. If the variable is missing or empty, a new key is generated,
printed to the console (so the administrator can persist it in a
``.env`` file), and used for the current session.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

# --------------------------------------------------------------------------- #
# Module-level logger configuration
# --------------------------------------------------------------------------- #
logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Public helper functions
# --------------------------------------------------------------------------- #
def generate_key() -> bytes:
    """
    Generate a new Fernet key.

    The returned key is a url-safe base64-encoded 32-byte value, suitable
    for constructing a :class:`~cryptography.fernet.Fernet` instance or
    for persisting in an environment variable.

    Returns
    -------
    bytes
        A fresh, url-safe base64-encoded Fernet key.
    """
    return Fernet.generate_key()


# --------------------------------------------------------------------------- #
# Internal key-loading logic
# --------------------------------------------------------------------------- #
def _load_or_create_key() -> bytes:
    """
    Load the Fernet key from the ``ENCRYPTION_KEY`` environment variable.

    If the variable is missing or empty, a new ephemeral key is generated,
    printed to the console (so the admin can copy it into a ``.env``
    file), and used for the current session only.

    Returns
    -------
    bytes
        The Fernet key to use for encryption / decryption.
    """
    raw_key: Optional[str] = os.environ.get("ENCRYPTION_KEY")

    if not raw_key:
        logger.warning(
            "ENCRYPTION_KEY environment variable is not set. "
            "Generating a new ephemeral key for this session only. "
            "Persist it in your .env file to avoid data loss."
        )
        new_key: bytes = generate_key()
        # Print to stdout so the admin can copy/paste it into .env
        print("=" * 72)
        print("NEW ENCRYPTION KEY GENERATED — save this to your .env file:")
        print(f"ENCRYPTION_KEY={new_key.decode('utf-8')}")
        print("=" * 72)
        return new_key

    return raw_key.encode("utf-8")


# --------------------------------------------------------------------------- #
# Module-level Fernet instance
#
# Fernet is thread-safe, so a single shared instance is appropriate for
# the entire application lifecycle.
# --------------------------------------------------------------------------- #
_fernet: Fernet = Fernet(_load_or_create_key())


# --------------------------------------------------------------------------- #
# Encryption / Decryption utility class
# --------------------------------------------------------------------------- #
class DataEncryptor:
    """
    Static utility class providing AES-based symmetric encryption and
    decryption for sensitive data (e.g., API tokens, user PII) before
    persistence in the database.

    All methods are :func:`~staticmethod` and rely on the module-level
    :data:`_fernet` instance, which is initialized from the
    ``ENCRYPTION_KEY`` environment variable when this module is first
    imported.
    """

    @staticmethod
    def encrypt(data: Optional[str]) -> Optional[str]:
        """
        Encrypt a UTF-8 plaintext string.

        The resulting Fernet token (url-safe base64 bytes) is decoded to
        a regular ``str`` so it can be stored directly in a database
        ``TEXT`` / ``VARCHAR`` column.

        Parameters
        ----------
        data : Optional[str]
            The plaintext string to encrypt. ``None`` is returned
            unchanged so callers can pipe nullable fields through
            transparently.

        Returns
        -------
        Optional[str]
            The encrypted token as a UTF-8 string, or ``None`` if
            ``data`` was ``None``.

        Raises
        ------
        TypeError
            If ``data`` is neither a ``str`` nor ``None``.
        Exception
            Any unrecoverable error raised by the underlying
            ``cryptography`` library (e.g. invalid key state). These are
            logged before re-raising.
        """
        if data is None:
            return None

        if not isinstance(data, str):
            raise TypeError(
                f"Expected 'str' or None for 'data', "
                f"got '{type(data).__name__}'."
            )

        try:
            token: bytes = _fernet.encrypt(data.encode("utf-8"))
            return token.decode("utf-8")
        except Exception:
            logger.exception("Failed to encrypt data.")
            raise

    @staticmethod
    def decrypt(encrypted_data: Optional[str]) -> Optional[str]:
        """
        Decrypt a token previously produced by :meth:`encrypt`.

        The method handles :class:`~cryptography.fernet.InvalidToken`
        safely by logging the error and returning ``None`` instead of
        propagating the exception. This prevents a single corrupted or
        tampered record from crashing the bot.

        Parameters
        ----------
        encrypted_data : Optional[str]
            The encrypted token (as returned by :meth:`encrypt`).
            ``None`` is returned unchanged.

        Returns
        -------
        Optional[str]
            The decrypted plaintext string, or ``None`` if:

            * ``encrypted_data`` was ``None``, or
            * the token was invalid, tampered with, generated with a
              different key, or otherwise malformed.

        Raises
        ------
        TypeError
            If ``encrypted_data`` is neither a ``str`` nor ``None``.
        """
        if encrypted_data is None:
            return None

        if not isinstance(encrypted_data, str):
            raise TypeError(
                f"Expected 'str' or None for 'encrypted_data', "
                f"got '{type(encrypted_data).__name__}'."
            )

        try:
            plaintext: bytes = _fernet.decrypt(encrypted_data.encode("utf-8"))
            return plaintext.decode("utf-8")
        except InvalidToken:
            logger.error(
                "InvalidToken encountered during decryption — the data "
                "may be tampered with, generated with a different key, "
                "or corrupted. Returning None."
            )
            return None
        except Exception:
            logger.exception(
                "Unexpected error during decryption. Returning None."
            )
            return None


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
__all__ = ["DataEncryptor", "generate_key"]