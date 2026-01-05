import os
import logging
import threading
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode
from flask import Flask

# Setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# Flask app for health checks
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "🤖 Telegram Bot is running on Choreo!"

@flask_app.route('/health')
def health():
    return 'OK', 200

@flask_app.route('/ping')
def ping():
    return 'pong', 200

def run_flask():
    """Run Flask server for health checks"""
    port = int(os.environ.get('PORT', 8080))
    flask_app.run(host='0.0.0.0', port=port, debug=False)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    keyboard = [
        [InlineKeyboardButton("✈️ Book Flights", callback_data="flights")],
        [InlineKeyboardButton("🚌 Book Buses", callback_data="buses")]
    ]
    
    await update.message.reply_text(
        "🚀 *Bot on Choreo is WORKING!*\nChoose service:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

def main():
    print("=" * 50)
    print("🤖 DEPLOYING ON CHOREO")
    print("=" * 50)
    
    if not TOKEN:
        print("❌ ERROR: TELEGRAM_BOT_TOKEN not set in Choreo!")
        print("Go to: Configure & Deploy → Environment Variables")
        return
    
    print(f"✅ Token found: {TOKEN[:10]}...")
    
    # Start Flask for health checks
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print("✅ Health check server started")
    
    # Start Telegram bot
    try:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(lambda u,c: u.callback_query.answer("✅")))
        
        print("✅ Telegram bot starting...")
        print("=" * 50)
        print("📱 Send /start to test!")
        print("=" * 50)
        
        app.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        print(f"❌ Bot error: {e}")

if __name__ == "__main__":
    main()
