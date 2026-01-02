<div align="center">

# 📥 Telegram Multi Downloader Bot

<img src="https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python">
<img src="https://img.shields.io/badge/Pyrogram-2.0-green?style=for-the-badge&logo=telegram&logoColor=white" alt="Pyrogram">
<img src="https://img.shields.io/badge/MongoDB-4.6-brightgreen?style=for-the-badge&logo=mongodb&logoColor=white" alt="MongoDB">
<img src="https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge" alt="License">

<br><br>

**🚀 A powerful Telegram bot to download files from Google Drive & Terabox with queue management, thumbnail generation, and premium features.**

[Features](#-features) • [Deploy](#-deploy-on-render) • [Commands](#-commands) • [Config](#-configuration) • [Credits](#-credits)

<br>

---

</div>

## ✨ Features

<table>
<tr>
<td>

### 📥 Download Sources
- ✅ Google Drive (Direct & Shared Links)
- ✅ Google Storage Links
- ✅ Terabox / 1024Tera
- ✅ Terabox Folders (Individual Files)
- ✅ Direct Download Links

</td>
<td>

### 🎬 Media Support
- ✅ Videos (MP4, MKV, AVI, etc.)
- ✅ Audio (MP3, WAV, FLAC, etc.)
- ✅ Images (JPG, PNG, GIF, etc.)
- ✅ Documents (PDF, ZIP, APK, etc.)

</td>
</tr>
<tr>
<td>

### 👑 Premium System
- ✅ Daily Limits for Free Users
- ✅ Unlimited for Premium Users
- ✅ Configurable File Size Limits
- ✅ Custom Settings for Premium

</td>
<td>

### 🛠️ Advanced Features
- ✅ Auto Thumbnail Generation
- ✅ Queue Management
- ✅ Progress Bar with ETA
- ✅ Flood Protection (Message Delay)

</td>
</tr>
</table>

---

## 🚀 Deploy on Render

### 📋 Prerequisites

| Requirement | Where to Get |
|-------------|--------------|
| Telegram API ID & Hash | [my.telegram.org](https://my.telegram.org) |
| Bot Token | [@BotFather](https://t.me/BotFather) |
| MongoDB URI | [MongoDB Atlas](https://www.mongodb.com/atlas) (Free) |

---

### 📝 Step 1: Fork Repository

1. Click the **Fork** button on this repository
2. Wait for the fork to complete

---

### 📝 Step 2: Create Render Account

1. Go to [render.com](https://render.com)
2. Sign up with your **GitHub account**

---

### 📝 Step 3: Create New Web Service

1. Click **"New +"** → **"Web Service"**
2. Connect your forked repository
3. Fill the following details:

| Field | Value |
|-------|-------|
| **Name** | `telegram-downloader-bot` |
| **Region** | `Singapore (Southeast Asia)` |
| **Branch** | `main` |
| **Root Directory** | *(Leave empty)* |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python main.py` |
| **Instance Type** | `Free` |

---

### 📝 Step 4: Add Environment Variables

Click **"Advanced"** → **"Add Environment Variable"**

| Key | Value | Required |
|-----|-------|----------|
| `PYTHON_VERSION` | `3.11.7` | ✅ |
| `API_ID` | Your Telegram API ID | ✅ |
| `API_HASH` | Your Telegram API Hash | ✅ |
| `BOT_TOKEN` | Bot token from @BotFather | ✅ |
| `MONGO_URI` | MongoDB connection string | ✅ |
| `START_PIC` | Start image URL | ❌ |
| `THUMBNAIL_URL` | Default thumbnail URL | ❌ |
| `TERABOX_COOKIE` | Terabox cookies (for better downloads) | ❌ |
| `MESSAGE_DELAY` | Delay between messages (default: 5) | ❌ |
| `PORT` | `8080` | ✅ |

---

### 📝 Step 5: Deploy!

1. Click **"Create Web Service"**
2. Wait for deployment (5-10 minutes)
3. Check logs for any errors
4. Your bot should be running! 🎉

---

## 📋 Commands

### 👤 User Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot |
| `/help` | Show help message |
| `/cancel` | Cancel ongoing task |

### 👑 Premium Commands (Owner Only)

| Command | Description |
|---------|-------------|
| `/premium <user_id> <days>` | Add premium to user |
| `/removepremium <user_id>` | Remove premium from user |
| `/broadcast` | Broadcast message to all users |

### ⚙️ Settings Commands (Premium Only)

| Command | Description |
|---------|-------------|
| `/setting` | Open settings menu |

---

## ⚙️ Configuration

### 📁 config.py

```python
# Freemium Limits
FREE_DAILY_LIMIT = 5          # Tasks per day
FREE_MAX_SIZE = 200 * 1024 * 1024  # 200 MB

# Premium Limits
PREMIUM_MAX_SIZE = 4 * 1024 * 1024 * 1024  # 4 GB

# Other Settings
MESSAGE_DELAY = 5             # Seconds between messages
PROGRESS_UPDATE_INTERVAL = 8  # Progress update interval

Premium vs Freemium
Feature	🆓 Freemium	💎 Premium
Daily Tasks	5	♾️ Unlimited
Max File Size	200 MB	4 GB
Download Speed	Normal	High Priority
Custom Settings	❌	✅
Custom Thumbnail

🗂️ Project Structure

TelegramDownloaderBot/
├── 📄 main.py              # Main entry point
├── 📄 config.py            # Configuration
├── 📄 requirements.txt     # Dependencies
├── 📄 runtime.txt          # Python version
├── 📄 render.yaml          # Render config
├── 📁 database/
│   ├── __init__.py
│   ├── mongodb.py          # Database connection
│   └── users.py            # User operations
├── 📁 handlers/
│   ├── __init__.py
│   ├── start.py            # Start command
│   ├── help.py             # Help command
│   ├── settings.py         # Settings handler
│   ├── broadcast.py        # Broadcast handler
│   ├── premium.py          # Premium handler
│   ├── cancel.py           # Cancel handler
│   ├── link_handler.py     # Link processing
│   └── file_handler.py     # File processing
└── 📁 utils/
    ├── __init__.py
    ├── progress.py         # Progress bar
    ├── downloader.py       # Download manager
    ├── uploader.py         # Upload manager
    ├── thumbnail.py        # Thumbnail generator
    ├── queue_manager.py    # Queue manager
    └── helpers.py          # Helper functions


yourusername/TelegramDownloaderBot?style=social" alt="Forks">
<br><br>


