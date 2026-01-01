# 🤖 Telegram Downloader Bot

A powerful Telegram bot to download files from Google Drive, Terabox, and direct links. Supports batch downloads, thumbnail generation, and premium features.

## ✨ Features

- 📥 Download from Google Drive, Terabox & Direct Links
- 📁 Auto-zip folder contents
- 🖼️ Thumbnail generation for all file types
- 📊 Real-time progress bar
- 📋 Queue system for multiple links
- 📝 Batch download from .txt files
- 👥 Group & Topic support
- 💎 Premium & Freemium tiers
- 📢 Broadcast system
- 📊 Detailed task summary

## 🚀 Deploy on Render

### Environment Variables

| Variable | Description |
|----------|-------------|
| `API_ID` | Telegram API ID |
| `API_HASH` | Telegram API Hash |
| `BOT_TOKEN` | Telegram Bot Token |
| `MONGO_URL` | MongoDB Connection URL |
| `START_PIC` | Start image URL |
| `DEFAULT_THUMBNAIL` | Default thumbnail URL for PDFs |

### Steps

1. Fork this repository
2. Create a new Web Service on Render
3. Connect your GitHub repo
4. Add environment variables
5. Deploy!

## 📝 Commands

- `/start` - Start the bot
- `/help` - Get help and usage guide
- `/settings` - Configure bot settings (Premium only)
- `/broadcast` - Broadcast message (Owner only)
- `/cancel` - Cancel ongoing task

## 👑 Premium vs Freemium

| Feature | Freemium | Premium |
|---------|----------|---------|
| Daily Tasks | 5 | Unlimited |
| Max File Size | 200 MB | 4 GB |
| Speed | Low | High |
| /settings | ❌ | ✅ |

## 👤 Owner

- Telegram: [@technicalserena](https://t.me/technicalserena)
- Contact: [@Xioqui_xin](https://t.me/Xioqui_xin)

## 📜 License

MIT License
