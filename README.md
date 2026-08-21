# ⚡ PHANTOM-X — Premium Telegram Userbot Master (v3.1)

**Master Bot (Aiogram v3)** + **Worker Userbot (Telethon)** — dono fixed, tested
aur server-ready. / Both fixed, tested and ready to run on a server.

> 🛠 **v3.1 — kya kya fix hua? (What was fixed)**
> • Saare userbot commands ab **outgoing-only** hain — koi stranger `.ban`
>   `.spam` type kar ke aapka bot trigger nahi kar sakta (bada security fix).
> • `Message.get_input_entity()` aur `client.delete_photos()` — ye methods
>   Telethon mein hain hi nahi the; `.clone` `.revert` `.delpfp` `.id` `.info`
>   `.pfp` `.raid` sab crash ho rahe the → **fixed**.
> • Deploy command fix: `python -m worker_bot.userbot` galat tha (module milta
>   hi nahi) → ab `python3 userbot.py` — deploy ab sach mein chalega.
> • Duplicate/conflicting commands (`.info`, `.admins`) resolve.
> • Master bot shutdown crash (`on_shutdown(bot, logger)` TypeError) fix.
> • Network drop hone pe bot mar jata tha → auto-reconnect + backoff loop.
> • Stealth monitor ab sach mein start hota hai (pehle kabhi start hi nahi
>   hota tha + AttributeError tha).
> • Telethon client leak fix (hosting flow), session strings ab **encrypted**
>   store hote hain (Fernet/AES).
> • `/getid` ka OTP button ab **real OTP** fetch karta hai (dummy nahi),
>   `/terminatesessions` bhi real hai.
> • `/logs <host>`, `/servers`, real "Kill All Userbots" button — naye admin
>   features.

> ✨ **v3.1.1 — aur naya (new in this release)**
> • **`/admin` dashboard** — pehle dead-code keyboard tha, ab poora working
>   panel (Stats / Broadcast / Settings / SSH / Special Panel — DB download,
>   all-users list, inactive users).
> • **OTP numpad** — hosting flow mein tap karke OTP daalo (calculator-style
>   keypad; typing bhi chalegi).
> • **`/adminhelp`** — saare admin commands ek jagah.
> • **`gen_session.py`** — SESSION_STRING one-command generator.
> • **`.gitignore`** — secrets / db / cache ab git mein ghusenge nahi.

---

## 📥 Is project ko git mein kaise daalein (3 easy tarike)

### ⭐ Tarika 1 — Pull Request merge (sabse easy, recommended)
Kaam branch `arena/01a0242f-k1` pe ready hai — GitHub par iska PR khula
hoga. Bas **"Merge pull request"** dabao, poora v3.1 `main` mein aa jayega.

```bash
# ya command-line se (main branch par):
git fetch origin
git merge origin/arena/01a0242f-k1
git push
```

### 📦 Tarika 2 — ZIP download → apna naya repo
1. **`phantom-x.zip`** download karo (file viewer se).
2. Extract karo, phir:
```bash
cd phantom-x
git init
git add .
git commit -m "PHANTOM-X v3.1 userbot"
git branch -M main
git remote add origin https://github.com/<username>/<repo>.git
git push -u origin main
```

### 🔗 Tarika 3 — Seedha branch clone karke apne repo mein push
```bash
git clone -b arena/01a0242f-k1 https://github.com/j66320238-crypto/k1.git phantom-x
cd phantom-x
git remote set-url origin https://github.com/<username>/<apna-repo>.git
git push -u origin main
```

> 💡 `.gitignore` included hai — `.env`, `*.session`, `*.db`,
> `__pycache__` automatic ignore hote hain.

---

## 📁 Structure

```
kuserbot/
├── main.py                    # Master bot entry point (aiogram v3)
├── config.py                  # .env loader + settings
├── database.py                # Async SQLite layer
├── encryption.py              # Fernet/AES helpers (session at rest)
├── handlers/                  # Master bot routers
│   ├── user.py                #   /start, hosting (phone→OTP numpad→2FA)
│   ├── normal_admin.py        #   /broadcast /stats /addhelp /adminhelp …
│   ├── special_admin.py       #   /getid (real OTP) /terminatesessions …
│   ├── panel.py               #   /admin dashboard (NEW)
│   ├── ssh_manager.py         #   SSH dashboard (add/del/kill servers)
│   └── deploy.py              #   /deploy /syncssh /logs /servers
├── keyboards/                 # Inline keyboards
├── utils/
│   ├── ssh_connector.py       # Async SSH/SFTP deploy engine
│   └── monitor.py             # Stealth inactivity monitor
└── worker_bot/                # Telethon USERBOT (deployed to servers)
    ├── userbot.py             #   ← entry point
    ├── core.py                #   compatibility shim (delegates)
    ├── gen_session.py         #   SESSION_STRING generator (NEW)
    └── modules/
        ├── admin.py           # .ban .kick .purge .lock .warn .gban …
        ├── animations.py      # 30+ animations (.hack .matrix .rain …)
        ├── afk.py             # .afk / .back (NEW)
        ├── antipm.py          # PM guard
        ├── info.py            # .info .sg .pfp .dc .me
        ├── misc.py            # .ping .sysinfo .calc .google (NEW)
        ├── profile.py         # .clone .revert .vo
        ├── raid.py            # .raid .drraid
        ├── spam.py            # .spam .uspam .mspam .gspam
        └── tags.py            # .tagall .onetag .tagadmins
```

---

## 🚀 Master Bot Setup (server pe chalane ke liye)

```bash
cd kuserbot

# 1) virtual env + deps + .env — sab ek command mein
./start.sh                  # pehli baar chalega, phir bot start

# -- OR manually --
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # ← BOT_TOKEN / API_ID / API_HASH / ADMIN_IDS bharo
python3 main.py
```

**.env values:**
| Key | Kahan se milega |
|---|---|
| `BOT_TOKEN` | @BotFather se |
| `API_ID`, `API_HASH` | my.telegram.org → API development tools |
| `ADMIN_IDS` | Apna Telegram user ID (comma separated) |
| `ENCRYPTION_KEY` | `python3 -c "from encryption import generate_key; print(generate_key().decode())"` |

**Auto-restart (systemd):** `phantom-x.service` file repo mein hai — install
steps file ke andar comment mein hain.

---

## 🤖 Userbot Commands (worker)

Kisi bhi chat mein `.help` bhejo — saare commands ki list aa jayegi.
Highlights:

| Category | Commands |
|---|---|
| 🎬 Animations | `.hack .dino .brain .moon .earth .matrix .bomb .rocket .loading .wave .dance .ghost .fire .shoot .stars .fuck .heart .clock` + **NEW:** `.loader .cointoss .dice .rain .snow .siren .fight .snake .love .ninja .countdown .typewriter .balloon` |
| 🛠 Admin | `.ban .unban .kick .promote .demote .mute .unmute .pin .unpin .purge .del .lock .unlock .autodelete .admins .warn .gban .antiflood` |
| 📡 Info | `.id .info .sg .common .pfp .uname .dc .me` |
| 💥 Spam | `.spam .uspam .fastspam .delayspam .dmspam .mspam .gspam .setgspam` |
| 🎯 Raid | `.setraid .raid .drraid .stopraid` |
| 🏷 Tags | `.tagall .onetag .tagadmins .cancel` |
| 🧰 Utils | `.alive .ping .uptime .sysinfo .calc .google .time .random .reverse .count .tasks .stop .help` |
| 😴 AFK | `.afk [reason]` / `.back` |
| 🛡 PM Guard | `.pmguard .approve .disapprove .setlimit .setpmmsg` |
| 👤 Profile | `.clone .revert .saveprofile .loadprofile .vo .setname .setbio .delpfp` |

Har animation ko rokne ke liye `.stop`.

---

## 🤖 Master Bot Commands

| Command | Kaam |
|---|---|
| `/start` | Main menu + hosting |
| `/admin` | **Admin dashboard** (stats, settings, SSH, DB download buttons) |
| `/adminhelp` | Saare admin commands ki list |
| `/broadcast <msg>` / reply | Broadcast live progress ke saath |
| `/stats` | Statistics |
| `/addhelp` `/delhelp` `/listhelp` | Help menu manage |
| `/setsupport` `/setowner` `/setfjoin` `/delfjoin` `/setwelcome` | Settings |
| `/ssh` | SSH server dashboard (add / delete / kill userbots) |
| `/servers` `/deploy <id>` `/syncssh` `/logs <host>` | Deploy tools |
| `/getid <phone>` `/terminatesessions <phone>` `/specialhelp` | Special admin |

**Hosting flow:** 📟 Click to Host → phone number → **OTP numpad se tap karke
ya type karke** OTP → 2FA password (agar hai) → session encrypted save ✅

---

## ☁️ Remote Deploy (master → SSH server)

1. Master bot mein `/ssh` → **➕ Add Server** (host/user/password).
2. `/deploy <telegram_user_id>` → worker files upload, pip install, userbot
   `nohup` pe start (PID wapas aayega).
3. `/logs <host> [lines]` → live log tail.
4. SSH dashboard → **⚡ Kill All Userbots** → sab userbots band.

> File-sync only (userbot start kiye bina): `/syncssh`

---

## 🧪 Self-test (deploy se pehle sab verify karo)

```bash
cd kuserbot
python3 -m py_compile $(git ls-files '*.py')   # syntax
python3 smoke_test.py                          # full wiring test
```

`smoke_test.py` checks: master-bot imports, database, keyboards, worker
module registration (10 modules / 250+ handlers), SSH connector, encryption
round-trip — bina network ke.

---

## ⚠️ Legal / ToS

Ye project sirf educational/reference ke liye hai. Spam/raid tools ka
galat istemal Telegram ToS ke khilaf hai — apne risk pe use karo.
