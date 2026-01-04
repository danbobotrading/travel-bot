import os
import logging
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode

# Setup
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    keyboard = [
        [InlineKeyboardButton("✈️ Book Flights", callback_data="flights")],
        [InlineKeyboardButton("🚌 Book Buses", callback_data="buses")],
        [InlineKeyboardButton("🏨 Book Hotels", callback_data="hotels")]
    ]
    
    await update.message.reply_text(
        "🚀 *Travel Bot is WORKING!*\n\nChoose service:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle buttons"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "flights":
        await query.edit_message_text("✈️ Flight booking coming soon!")
    elif query.data == "buses":
        await query.edit_message_text("🚌 Bus booking coming soon!")
    elif query.data == "hotels":
        await query.edit_message_text("🏨 Hotel booking coming soon!")

def main():
    print("=" * 50)
    print("🤖 BACKGROUND WORKER STARTING")
    print("=" * 50)
    
    if not TOKEN:
        print("❌ ERROR: TELEGRAM_BOT_TOKEN not set!")
        print("Add in Render Environment Variables")
        return
    
    print(f"✅ Token found: {TOKEN[:10]}...")
    
    try:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CallbackQueryHandler(button_handler))
        
        print("✅ Bot starting...")
        print("=" * 50)
        print("📱 Send /start to test!")
        print("=" * 50)
        
        app.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
