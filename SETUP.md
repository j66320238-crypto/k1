# 🚀 PHANTOM-X — Complete Setup Guide (Step-by-Step)

> Ye guide Roman Urdu + English mein hai. Bas order mein follow karo —
> 15-20 minute mein bot ready. / Follow these steps in order.

---

## 📋 Step 0 — Kya-kya chahiye (What you need)

| Cheez | Kahan se |
|---|---|
| 🖥 Server / VPS / PC | Linux (Ubuntu/Debian best) ya Termux (phone) |
| 🐍 Python 3.10+ | `python3 --version` se check karo |
| 🤖 BOT_TOKEN | @BotFather (Telegram) se |
| 🔑 API_ID + API_HASH | my.telegram.org se |
| 🆔 Apna Telegram ID | @userinfobot se |

---

## 🔑 Step 1 — Token & IDs nikalna (Get credentials)

### 1A. BOT_TOKEN (bot ke liye)
1. Telegram kholo → search karo **@BotFather**
2. `/newbot` bhejo
3. Bot ka **name** likho (e.g. `My Phantom Bot`)
4. Bot ka **username** likho — end mein `bot` hona chahiye (e.g. `phantom_x_bot`)
5. BotFather ek **token** dega aisa:
   ```
   123456789:AAHfk3nSs2xvX9qLmZ4tYbC8dE1fGhIjKlM
   ```
6. **Copy karke save kar lo** — isi ko `.env` mein dalenge.

### 1B. API_ID + API_HASH (user account login ke liye)
1. Browser mein jao: **https://my.telegram.org**
2. Apna **phone number** (+91...) daal kar login karo
   (Telegram app pe code aayega)
3. **API development tools** pe click karo
4. App banao:
   - App title: kuch bhi (e.g. `phantom`)
   - Short name: kuch bhi
   - Platform: koi bhi
5. Page pe milega:
   ```
   App api_id:  1234567          ← ye API_ID hai
   App api_hash: abcdef123456... ← ye API_HASH hai
   ```
6. Dono **copy kar lo**.

### 1C. Apna Telegram user ID
1. Telegram mein **@userinfobot** ko koi bhi message bhejo
2. Wo aapka **Id: 123456789** bata dega ← ye ADMIN_IDS ke liye hai

---

## 📂 Step 2 — Project server pe dalna (Get the code)

### Tarika A — ZIP se
```bash
# zip upload karo server pe (SCP/File Manager se), phir:
unzip phantom-x-v3.1.zip
cd phantom-x/kuserbot     # (ya kuserbot — jahan main.py hai)
```

### Tarika B — Git se
```bash
git clone https://github.com/j66320238-crypto/k1.git phantom-x
cd phantom-x/kuserbot
```

> ⚠️ Important: `.env` file **usi folder mein banao jahan `main.py` hai**
> (yani `kuserbot/` ke andar).

---

## ✏️ Step 3 — BOT_TOKEN wagaira dalna (.env file)

```bash
cd kuserbot                          # main.py wale folder mein
cp .env.example .env                 # template copy
nano .env                            # ya vi .env
```

File ko aise bharo:

```env
BOT_TOKEN=123456789:AAHfk3nSs2xvX9qLmZ4tYbC8dE1fGhIjKlM
API_ID=1234567
API_HASH=abcdef1234567890abcdef
ADMIN_IDS=7839547993
ENCRYPTION_KEY=
```

| Value | Kya dalna hai |
|---|---|
| `BOT_TOKEN` | Step 1A wala poora token (spaces ke bina) |
| `API_ID` | Step 1B wala **number** |
| `API_HASH` | Step 1B wala lamba hash |
| `ADMIN_IDS` | Step 1C wala **aapki ID** (multiple: `111,222`) |
| `ENCRYPTION_KEY` | Step 4 mein generate karenge, phir yahan paste |

Save: `Ctrl+O`, Enter, `Ctrl+X` (nano mein)

---

## 🔐 Step 4 — ENCRYPTION_KEY generate karna

Pehle ek baar dependencies install karo (dekho Step 5), phir `kuserbot`
folder mein ye command chalao:

```bash
cd kuserbot
source .venv/bin/activate        # agar start.sh pehle chala ho
python3 -c "from encryption import generate_key; print(generate_key().decode())"
```

Ek key print hogi:
```
NhX3zCx81d77A3lwgkM9YmcFZNkDT7WGrv1hctiXPJQ=
```

Isko **copy karke** `.env` mein paste karo:
```env
ENCRYPTION_KEY=NhX3zCx81d77A3lwgkM9YmcFZNkDT7WGrv1hctiXPJQ=
```

> ⚠️ Ye key **backup kar lo** (kahi safe likh lo). Ye gumi to sab hosted
> sessions kho jayenge. Isko kisi ko mat dena.

---

## ▶️ Step 5 — Bot START karna

### Aasan tarika (recommended):
```bash
cd kuserbot
chmod +x start.sh        # sirf pehli baar
./start.sh
```

`start.sh` khud sab karega:
- ✅ `.venv` virtual environment banayega
- ✅ `pip install -r requirements.txt` (aiogram, telethon, paramiko...)
- ✅ `.env` check karega (nahi hai to template se bana dega)
- ✅ Bot start karega

Terminal pe aisa dikhega:
```
██████╗ ██╗  ██╗ ██████╗ ███╗   ███╗███████╗██╗  ██╗ ██████╗ ███╗   ██╗
...
✓ Router registered: special_admin
✓ Router registered: panel
✓ Router registered: normal_admin
✓ Router registered: user
✓ Router registered: ssh_manager
✓ Router registered: deploy
● Starting long-polling…
✓ Database initialised successfully.
║  🟢  BOT IS NOW ONLINE
```

**🟢 BOT IS NOW ONLINE** dikha? Ho gaya! 🎉

### Manual tarika (agar .venv nahi chahiye):
```bash
cd kuserbot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

---

## ✅ Step 6 — Bot test karna

1. Telegram mein apne bot ko kholo (username jo BotFather pe banaya)
2. `/start` bhejo → menu aayega
3. `/admin` bhejo → admin dashboard khulega (Stats, Settings, SSH...)
4. `/adminhelp` → saare commands dikhenge

Bot start hote hi **special admin** ko 🟢 online message bhi aayega.

---

## 🤖 Step 7 — Userbot chalana (accounts host karna)

Master bot se **bina SSH server** bhi userbot session bana sakte ho:

### Option A — Master bot se (easy)
1. Bot mein `/start` → **📟 Click to Host**
2. Phone number bhejo: `+919876543210`
3. Telegram app mein OTP aayega → **numpad pe tap karke** ya type karke bhejo
4. 2FA password hai to wo bhejo
5. ✅ Session ban gaya — **encrypted** save ho gaya DB mein

### Option B — Termux/PC pe directly userbot
```bash
cd kuserbot
pip install telethon
python3 worker_bot/gen_session.py
```
API_ID, API_HASH, phone, OTP poochega → **SESSION_STRING** dega.
Phir:
```bash
export API_ID=1234567
export API_HASH=abcdef123
export SESSION_STRING='BADA-SESSION-STRING-YAHAN'
python3 worker_bot/userbot.py
```
`🚀 Userbot is online` dikhega. Kisi bhi chat mein `.alive` ya `.help` bhejo.

---

## ☁️ Step 8 — SSH server pe deploy (optional, multi-user ke liye)

1. Master bot mein `/ssh` → **➕ Add Server**
2. Teeno cheezein bhejo (ek-ek karke):
   - SSH Host (e.g. `ssh-user.alwaysdata.net`)
   - SSH Username
   - SSH Password
3. ✅ Server add hoga
4. Kisi user ka hosting complete hone ke baad:
   `/deploy <user_id>` → files upload + install + userbot start (PID milega)
5. `/logs <host>` → live logs dekho
6. SSH dashboard → **⚡ Kill All Userbots** → sab band

Sirf files update karni hain? → `/syncssh`

---

## 🔁 Step 9 — Hamesha ON rakhna (auto-restart)

### systemd (VPS pe best):
```bash
cd kuserbot
# pehle path edit karo file ke andar (nano phantom-x.service):
#   WorkingDirectory=/path/to/kuserbot
sudo cp phantom-x.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now phantom-x

# status / logs:
sudo systemctl status phantom-x
journalctl -u phantom-x -f
```

### nohup (quick tarika):
```bash
cd kuserbot
source .venv/bin/activate
nohup python3 main.py > bot.log 2>&1 &
tail -f bot.log
```

---

## 📱 Termux (phone) pe chalana

```bash
pkg update && pkg install python git -y
git clone https://github.com/j66320238-crypto/k1.git phantom-x
cd phantom-x/kuserbot
pip install -r requirements.txt
cp .env.example .env && nano .env       # values bharo
python3 main.py
```
> Termux ko alive rakhne ke liye notification allow karo + battery
> optimization band karo, warna phone sleep pe bot band ho jayega.

---

## 🛠 Common Problems & Solutions

| Problem | Fix |
|---|---|
| `BOT_TOKEN is not set` | `.env` file `main.py` wale folder mein hai? Values bhari hain? |
| `TelegramTokenError / token invalid` | BotFather se token dobara copy karo (extra space mat lo) |
| `pip: command not found` | `apt install python3-pip -y` (ya Termux: `pkg install python`) |
| `Permission denied: ./start.sh` | `chmod +x start.sh` |
| Bot start hote hi band | Terminal ka error padho — 99% `.env` galat hai |
| `python3: command not found` (Windows) | Python.org se install + "Add to PATH" tick karo |
| OTP nahi aa raha login pe | Telegram app ka notification check karo; `+` country code ke saath number |
| Session kaam nahi kar raha | `/deploy` dobara karo ya naya session banao (purana revoke ho sakta hai) |
| Userbot band ho gaya restart ke baad | systemd use karo (Step 9) — auto-restart |
| `ENCRYPTION_KEY` warning boot pe | `.env` mein key daal do (Step 4) — nahi to sessions har restart pe lost |

---

## 📝 Ek nazar mein (TL;DR)

```bash
# 1. code lo          → 2. folder mein .env banao       → 3. values dalo
git clone <repo>         cd kuserbot                      BOT_TOKEN, API_ID,
                         cp .env.example .env             API_HASH, ADMIN_IDS,
                                                          ENCRYPTION_KEY
# 4. install + start
chmod +x start.sh && ./start.sh        # → 🟢 BOT IS NOW ONLINE
# 5. test
# Telegram: /start → /admin → 📟 Host → phone → OTP → done ✅
```

Koi dikkat aaye to `bot.log` (master) ya `userbot.log` (worker) check karo —
error wahi dikhega. 🚀
