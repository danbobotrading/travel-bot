#!/usr/bin/env python3
"""
Simplest Telegram Travel Bot
Just responds to /start and /search
"""

import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters

# Get token from environment
TOKEN = os.getenv("TELEGRAM_TOKEN")

async def start(update: Update, context):
    """Handle /start command"""
    await update.message.reply_text(
        "✈️ Travel Bot Started!\n"
        "Use /search to find flights\n"
        "Use /help for assistance"
    )

async def search(update: Update, context):
    """Handle /search command"""
    await update.message.reply_text(
        "🔍 Flight search coming soon!\n"
        "Next step: Add API integration"
    )

async def help_command(update: Update, context):
    """Handle /help command"""
    await update.message.reply_text(
        "Help:\n"
        "/start - Start the bot\n"
        "/search - Find flights\n"
        "/help - This message"
    )

async def echo(update: Update, context):
    """Echo any text message"""
    await update.message.reply_text(
        f"You said: {update.message.text}\n"
        "Try /search instead"
    )

def main():
    """Run the bot"""
    if not TOKEN:
        print("❌ ERROR: Set TELEGRAM_TOKEN environment variable")
        print("Example: export TELEGRAM_TOKEN='your_token_here'")
        return
    
    # Create bot application
    app = Application.builder().token(TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("help", help_command))
    
    # Echo any text message
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))
    
    print("✅ Bot is running... (Press Ctrl+C to stop)")
    app.run_polling()

if __name__ == "__main__":
    main()
