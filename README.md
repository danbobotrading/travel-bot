# 🚀 Travel Deals Telegram Bot

A Telegram bot for booking flights, buses, and hotels with affiliate commissions.

## ✨ Features
- ✈️ Flight booking (One-way & Return)
- 🚌 Bus booking in South Africa
- 🏨 Hotels (coming soon)
- 🚢 Cruises (coming soon)
- 💰 Affiliate commission links
- 📱 Beautiful Telegram interface

## 🚀 Quick Deploy

### 1. Create Telegram Bot
1. Message @BotFather on Telegram
2. Send `/newbot`
3. Follow prompts
4. **SAVE THE TOKEN**

### 2. Deploy to Render
1. Click this button: [![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)
2. Connect your GitHub
3. Add environment variable: `TELEGRAM_BOT_TOKEN = your_token_here`
4. Click "Deploy"

### 3. Test Your Bot
1. Find your bot on Telegram
2. Send `/start`
3. Start booking!

## 🔧 Environment Variables

| Variable | Description |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | From @BotFather (required) |
| `TRAVELPAYOUTS_API_TOKEN` | For real flight data (optional) |
| `BUS_API_TOKEN` | For real bus data (optional) |

## 📁 Project Structure
