<div align="center">

# 📥 Telegram Multi Downloader Bot

<br>

<img src="https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python">
<img src="https://img.shields.io/badge/Pyrogram-2.0-green?style=for-the-badge&logo=telegram&logoColor=white" alt="Pyrogram">
<img src="https://img.shields.io/badge/MongoDB-4.6-brightgreen?style=for-the-badge&logo=mongodb&logoColor=white" alt="MongoDB">
<img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="License">

<br><br>

### 🚀 A powerful Telegram bot to download files from Google Drive & Terabox

**Queue management • Thumbnail generation • Premium features**

<br>

---

</div>

<br>

## ✨ Features

<br>

### 📥 Supported Sources

| Source | Status |
|--------|--------|
| Google Drive | ✅ Working |
| Google Storage | ✅ Working |
| Terabox | ✅ Working |
| 1024Tera | ✅ Working |
| Terabox Folders | ✅ Working |
| Direct Links | ✅ Working |

<br>

### 🎬 Supported Media

| Type | Extensions |
|------|------------|
| Video | MP4, MKV, AVI, MOV, WEBM |
| Audio | MP3, WAV, FLAC, AAC, OGG |
| Image | JPG, PNG, GIF, WEBP |
| Document | PDF, ZIP, RAR, APK |

<br>

### 👑 Premium System

| Feature | Free | Premium |
|---------|------|---------|
| Daily Tasks | 5 | ♾️ Unlimited |
| Max Size | 200 MB | 4 GB |
| Speed | Normal | High |
| Settings | ❌ | ✅ |

<br>

---

<br>

## 🚀 Deploy on Render

<br>

### 📋 Requirements

| Item | Link |
|------|------|
| Telegram API | [my.telegram.org](https://my.telegram.org) |
| Bot Token | [@BotFather](https://t.me/BotFather) |
| MongoDB | [mongodb.com/atlas](https://www.mongodb.com/atlas) |

<br>

### 📝 Step 1: Fork Repository

Click the **Fork** button on top right

<br>

### 📝 Step 2: Render Setup

1. Go to [render.com](https://render.com)
2. Sign up with **GitHub**
3. Click **"New +"** → **"Web Service"**
4. Connect your forked repo

<br>

### 📝 Step 3: Service Settings

| Setting | Value |
|---------|-------|
| **Name** | `telegram-downloader-bot` |
| **Region** | `Singapore` |
| **Branch** | `main` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python main.py` |
| **Instance** | `Free` |

<br>

### 📝 Step 4: Environment Variables

Click **"Advanced"** → **"Add Environment Variable"**

| Key | Value | Required |
|-----|-------|----------|
| `PYTHON_VERSION` | `3.11.7` | ✅ |
| `API_ID` | Your API ID | ✅ |
| `API_HASH` | Your API Hash | ✅ |
| `BOT_TOKEN` | Bot token | ✅ |
| `MONGO_URI` | MongoDB URL | ✅ |
| `PORT` | `8080` | ✅ |
| `START_PIC` | Image URL | ❌ |
| `THUMBNAIL_URL` | Thumb URL | ❌ |
| `TERABOX_COOKIE` | Cookies | ❌ |
| `MESSAGE_DELAY` | `5` | ❌ |

<br>

### 📝 Step 5: Deploy!

1. Click **"Create Web Service"**
2. Wait 5-10 minutes
3. Bot is ready! 🎉

<br>

---

<br>

## 📋 Commands

<br>

### 👤 User Commands

| Command | Description |
|---------|-------------|
| `/start` | Start bot |
| `/help` | Help message |
| `/cancel` | Cancel task |

<br>

### 👑 Owner Commands

| Command | Description |
|---------|-------------|
| `/premium <id> <days>` | Add premium |
| `/removepremium <id>` | Remove premium |
| `/broadcast` | Broadcast message |

<br>

### ⚙️ Settings (Premium)

| Command | Description |
|---------|-------------|
| `/setting` | Settings menu |

<br>

---

<br>

## 📊 Progress Bar

Downloading
video_file.mp4
to my server

[●●●●●○○○○○○○○○○○○○○○]

◌ Progress😉: 〘 25.00% 〙
Done: 〘87.65 MB of 350.61 MB〙
◌ Speed🚀: 〘 5.34 MB/s 〙
◌ Time Left⏳: 〘 49s 〙

text


<br>

---

<br>

## 🔧 Troubleshooting

<br>

| Error | Solution |
|-------|----------|
| Module not found | `pip install -r requirements.txt` |
| MongoDB failed | Check URI & whitelist `0.0.0.0/0` |
| Bot not responding | Check handlers in logs |
| Terabox failed | Add `TERABOX_COOKIE` |

<br>

---

<br>

## 📁 Project Structure

TelegramDownloaderBot/
├── main.py
├── config.py
├── requirements.txt
├── runtime.txt
├── database/
│ ├── init.py
│ ├── mongodb.py
│ └── users.py
├── handlers/
│ ├── init.py
│ ├── start.py
│ ├── help.py
│ ├── settings.py
│ ├── broadcast.py
│ ├── premium.py
│ ├── cancel.py
│ ├── link_handler.py
│ └── file_handler.py
└── utils/
├── init.py
├── progress.py
├── downloader.py
├── uploader.py
├── thumbnail.py
├── queue_manager.py
└── helpers.py

<br>

---

<br>

<div align="center">

## 👨‍💻 Developer & Credits

<br>

### Connect with me

<br>

<a href="https://t.me/technicalserena">
<img src="https://img.shields.io/badge/Telegram-2CA5E0?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram">
</a>

<br><br>

<a href="https://instagram.com/prince572002">
<img src="https://img.shields.io/badge/Instagram-E4405F?style=for-the-badge&logo=instagram&logoColor=white" alt="Instagram">
</a>

<br><br>

---

<br>

### ⭐ Star this repo if you like it!

<br>

<img src="https://img.shields.io/github/stars/prince572002/TelegramDownloaderBot?style=social" alt="Stars">
<img src="https://img.shields.io/github/forks/prince572002/TelegramDownloaderBot?style=social" alt="Forks">

<br><br>

---

<br>

### 💖 Made with Love by Prince

<br>

**© 2026 - MIT License**

</div>

