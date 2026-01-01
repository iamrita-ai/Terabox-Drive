# 📥 Telegram Multi Downloader Bot

A powerful Telegram bot to download files from **Google Drive** and **Terabox** with queue management, thumbnail generation, and premium features.

## ✨ Features

- 📥 Download from Google Drive & Terabox direct links
- 📁 Auto-zip folder contents
- 🖼️ Thumbnail generation for video/jpg/pdf/apk/mp3
- 📊 Queue management with progress tracking
- 📝 Support .txt file with multiple links
- 👥 Works in Groups & Topics
- 💎 Premium & Freemium system
- 📢 Broadcast system
- 📋 Detailed logging

## 🚀 Deploy on Render

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com)

### Environment Variables

| Variable | Description |
|----------|-------------|
| `API_ID` | Telegram API ID from my.telegram.org |
| `API_HASH` | Telegram API Hash from my.telegram.org |
| `BOT_TOKEN` | Bot token from @BotFather |
| `MONGO_URI` | MongoDB connection string |
| `START_PIC` | Start picture URL |
| `THUMBNAIL_URL` | Default thumbnail URL for PDFs |

## 📋 Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot |
| `/help` | Show help message |
| `/setting` | User settings (Premium only) |
| `/cancel` | Cancel ongoing task |
| `/broadcast` | Broadcast message (Owner only) |
| `/premium` | Add premium user (Owner only) |
| `/removepremium` | Remove premium (Owner only) |

## 💎 Limits

| Feature | Freemium | Premium |
|---------|----------|---------|
| Daily Tasks | 5 | Unlimited |
| Max File Size | 200 MB | 4 GB |
| Speed | Low | High |
| Settings | ❌ | ✅ |

## 📝 License

MIT License - Feel free to modify and use!

## 👨‍💻 Developer

- [@technicalserena](https://t.me/technicalserena)
- [@Xioqui_xin](https://t.me/Xioqui_xin)
