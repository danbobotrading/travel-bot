# Add these imports at the top
import cachetools
import hashlib
from datetime import datetime, timedelta

# Add cache setup (after imports)
flight_cache = cachetools.TTLCache(maxsize=100, ttl=900)  # 15 minute cache
bus_cache = cachetools.TTLCache(maxsize=50, ttl=1800)  # 30 minute cache

def get_cache_key(service: str, **kwargs):
    """Generate cache key from parameters"""
    key_string = f"{service}:{':'.join(f'{k}={v}' for k, v in sorted(kwargs.items()))}"
    return hashlib.md5(key_string.encode()).hexdigest()
    
import os
import logging
import json
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from telegram.constants import ParseMode
from api_clients import TravelPayoutsClient, BusBookingClient
from city_database import CityDatabase
from keep_alive import keep_alive

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Get bot token from environment
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

# Conversation states
MAIN_MENU, FLIGHT_TYPE, DEPARTURE_CITY, DESTINATION_CITY, DEPARTURE_DATE, RETURN_DATE, BUS_DEPARTURE, BUS_DESTINATION, BUS_DATE = range(9)

# Store user sessions
user_sessions = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message with main menu"""
    user_id = update.effective_user.id
    user_sessions[user_id] = {"service": None}
    
    keyboard = [
        [InlineKeyboardButton("✈️ Flights", callback_data="service_flights")],
        [InlineKeyboardButton("🚌 Buses", callback_data="service_buses")],
        [InlineKeyboardButton("🏨 Hotels", callback_data="service_hotels")],
        [InlineKeyboardButton("🚢 Cruises", callback_data="service_cruises")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
    ]
    
    await update.message.reply_text(
        "🌟 *Travel Deals Bot*\n\n"
        "Book flights, buses, hotels with affiliate commissions!\n"
        "Choose a service to begin:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return MAIN_MENU

async def handle_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle service selection"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    if query.data == "service_flights":
        user_sessions[user_id]["service"] = "flights"
        
        keyboard = [
            [InlineKeyboardButton("🛫 One Way", callback_data="flight_oneway")],
            [InlineKeyboardButton("🔄 Return", callback_data="flight_return")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
        ]
        
        await query.edit_message_text(
            "✈️ *FLIGHT BOOKING*\n\nSelect flight type:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return FLIGHT_TYPE
        
    elif query.data == "service_buses":
        user_sessions[user_id]["service"] = "buses"
        
        await query.edit_message_text(
            "🚌 *BUS BOOKING*\n\n"
            "📍 Enter departure city (e.g., Cape Town):",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
            ])
        )
        return BUS_DEPARTURE
        
    elif query.data in ["service_hotels", "service_cruises"]:
        await query.edit_message_text(
            "🛠️ *Coming Soon!*\n\n"
            f"{'🏨 Hotels' if 'hotels' in query.data else '🚢 Cruises'} feature is under development.\n"
            "Try our flight or bus booking instead!",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✈️ Flights", callback_data="service_flights"),
                 InlineKeyboardButton("🚌 Buses", callback_data="service_buses")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_main")]
            ])
        )
        return MAIN_MENU
        
    elif query.data == "back_main":
        return await start_callback(update, context)
        
    elif query.data == "help":
        await query.edit_message_text(
            "*📚 HOW TO USE*\n\n"
            "1. Select a service (Flights, Buses, etc.)\n"
            "2. Follow the step-by-step prompts\n"
            "3. Get real-time prices with affiliate links\n"
            "4. Book directly through our partners\n\n"
            "*💡 TIPS*\n"
            "• Type city names naturally\n"
            "• Use any date format\n"
            "• Click 'Load More' for more options\n"
            "• All bookings earn us commission\n\n"
            "*🔄 RESTART*\n"
            "Use /start anytime",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✈️ Book Flights", callback_data="service_flights")],
                [InlineKeyboardButton("🚌 Book Buses", callback_data="service_buses")],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="back_main")]
            ])
        )
        return MAIN_MENU

async def flight_type_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle flight type selection"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    if query.data == "flight_oneway":
        user_sessions[user_id]["flight_type"] = "oneway"
    elif query.data == "flight_return":
        user_sessions[user_id]["flight_type"] = "return"
    elif query.data == "back_main":
        return await start_callback(update, context)
    
    await query.edit_message_text(
        "📍 *DEPARTURE CITY*\n\n"
        "Type departure city (e.g., Cape Town):\n"
        "_You can also use airport codes like CPT or JNB_",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="service_flights")]
        ])
    )
    return DEPARTURE_CITY

async def departure_city_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle departure city input"""
    user_id = update.effective_user.id
    city_query = update.message.text
    
    # Search for cities
    cities = CityDatabase.search_cities(city_query)
    
    if not cities:
        await update.message.reply_text(
            "❌ City not found. Please try again:\n"
            "• Cape Town\n• Johannesburg\n• Durban\n• Pretoria\n• Or airport code (CPT, JNB, DUR)",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="service_flights")]
            ])
        )
        return DEPARTURE_CITY
    
    # Store and show options
    user_sessions[user_id]["city_options"] = cities
    
    # Create buttons for each city/airport
    keyboard = []
    for city in cities[:5]:  # Show max 5
        if city.get("airports"):
            for airport in city["airports"][:2]:  # Show max 2 airports per city
                btn_text = f"✈️ {airport['name']} ({airport['code']})"
                callback_data = f"depart_select:{airport['code']}:{city['name']}"
                keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback_data)])
        else:
            btn_text = f"📍 {city['name']}, {city['country']}"
            callback_data = f"depart_city:{city['name']}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback_data)])
    
    keyboard.append([InlineKeyboardButton("🔍 Search Again", callback_data="search_again_depart")])
    
    await update.message.reply_text(
        f"🔍 Found {len(cities)} location(s):\nSelect departure airport:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DEPARTURE_CITY

async def departure_select_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle departure airport selection"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    if query.data.startswith("depart_select:"):
        _, code, city = query.data.split(":")
        user_sessions[user_id]["departure"] = {"code": code, "city": city}
        
        await query.edit_message_text(
            f"✅ Departure: {city} ({code})\n\n"
            "📍 *DESTINATION CITY*\n\n"
            "Type destination city (e.g., Johannesburg):",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="search_again_depart")]
            ])
        )
        return DESTINATION_CITY
    
    elif query.data == "search_again_depart":
        await query.edit_message_text(
            "Type departure city again:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="service_flights")]
            ])
        )
        return DEPARTURE_CITY

async def destination_city_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle destination city input"""
    user_id = update.effective_user.id
    city_query = update.message.text
    
    cities = CityDatabase.search_cities(city_query)
    
    if not cities:
        await update.message.reply_text(
            "City not found. Please try again:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="search_again_depart")]
            ])
        )
        return DESTINATION_CITY
    
    user_sessions[user_id]["dest_options"] = cities
    
    keyboard = []
    for city in cities[:5]:
        if city.get("airports"):
            for airport in city["airports"][:2]:
                btn_text = f"✈️ {airport['name']} ({airport['code']})"
                callback_data = f"dest_select:{airport['code']}:{city['name']}"
                keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback_data)])
        else:
            btn_text = f"📍 {city['name']}, {city['country']}"
            callback_data = f"dest_city:{city['name']}"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback_data)])
    
    keyboard.append([InlineKeyboardButton("🔍 Search Again", callback_data="search_again_dest")])
    
    await update.message.reply_text(
        f"Found {len(cities)} location(s):\nSelect destination airport:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return DESTINATION_CITY

async def destination_select_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle destination selection"""
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    
    if query.data.startswith("dest_select:"):
        _, code, city = query.data.split(":")
        user_sessions[user_id]["destination"] = {"code": code, "city": city}
        
        dep_city = user_sessions[user_id]["departure"]["city"]
        dep_code = user_sessions[user_id]["departure"]["code"]
        
        await query.edit_message_text(
            f"✅ Route: {dep_city} ({dep_code}) → {city} ({code})\n\n"
            "📅 *DEPARTURE DATE*\n\n"
            "Enter departure date:\n"
            "_Formats: 20 Jan, 2024-01-20, tomorrow, next Friday_",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="search_again_dest")]
            ])
        )
        return DEPARTURE_DATE
    
    elif query.data == "search_again_dest":
        await query.edit_message_text(
            "Type destination city again:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="search_again_depart")]
            ])
        )
        return DESTINATION_CITY

async def departure_date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle departure date input"""
    user_id = update.effective_user.id
    date_str = update.message.text
    
    try:
        # Simple date parsing (in real app, use dateutil)
        if date_str.lower() in ["tomorrow", "tmrw"]:
            from datetime import timedelta
            dep_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            # Try to parse common formats
            for fmt in ["%d %b", "%d %B", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]:
                try:
                    dep_date = datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
                    break
                except:
                    continue
            else:
                raise ValueError("Date format not recognized")
        
        user_sessions[user_id]["departure_date"] = dep_date
        
        if user_sessions[user_id].get("flight_type") == "return":
            await update.message.reply_text(
                f"✅ Departure: {dep_date}\n\n"
                "📅 *RETURN DATE*\n\n"
                "Enter return date:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="search_again_dest")]
                ])
            )
            return RETURN_DATE
        else:
            # One-way - show results
            return await show_flight_results(update, context)
            
    except Exception as e:
        await update.message.reply_text(
            "❌ Invalid date. Please use formats like:\n"
            "• 20 Jan\n• 2024-01-20\n• tomorrow\n• next Friday",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="search_again_dest")]
            ])
        )
        return DEPARTURE_DATE

async def return_date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle return date input"""
    user_id = update.effective_user.id
    date_str = update.message.text
    
    try:
        if date_str.lower() in ["tomorrow", "tmrw"]:
            from datetime import timedelta
            ret_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            for fmt in ["%d %b", "%d %B", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]:
                try:
                    ret_date = datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
                    break
                except:
                    continue
            else:
                raise ValueError("Date format not recognized")
        
        user_sessions[user_id]["return_date"] = ret_date
        return await show_flight_results(update, context)
        
    except:
        await update.message.reply_text(
            "Invalid date format. Please try again:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="search_again_dest")]
            ])
        )
        return RETURN_DATE

async def show_flight_results(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show flight search results with REAL API"""
    user_id = update.effective_user.id
    session = user_sessions[user_id]
    
    # Show searching message
    if update.message:
        msg = await update.message.reply_text("🔍 Searching REAL flights via TravelPayouts...")
    else:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("🔍 Searching REAL flights via TravelPayouts...")
    
    try:
        # Generate cache key
        cache_key = get_cache_key(
            service="flights",
            origin=session["departure"]["code"],
            destination=session["destination"]["code"],
            departure_date=session["departure_date"],
            return_date=session.get("return_date", ""),
            currency="USD"
        )
        
        # Check cache first
        if cache_key in flight_cache:
            print("✅ Using cached flight results")
            flights = flight_cache[cache_key]
        else:
            # Get REAL flights from TravelPayouts API
            flights = await TravelPayoutsClient.search_flights(
                origin=session["departure"]["code"],
                destination=session["destination"]["code"],
                departure_date=session["departure_date"],
                return_date=session.get("return_date"),
                currency="USD",  # Or detect user currency
                limit=20  # Get more for "Load More" feature
            )
            
            # Cache the results
            flight_cache[cache_key] = flights
        
        if not flights:
            error_msg = (
                "❌ No flights found for your search.\n\n"
                "**Try:**\n"
                "• Different dates\n"
                "• Nearby airports\n"
                "• Flexible travel dates\n\n"
                "Or contact support if this persists."
            )
            keyboard = [[InlineKeyboardButton("🔄 New Search", callback_data="service_flights")]]
        else:
            # Format results
            session["search_results"] = flights
            session["results_offset"] = 0
            
            # Show first 3 cheapest flights
            results_text = format_flight_results(flights[:3], 1)
            
            # Add stats
            stats_text = (
                f"\n📊 **Stats:** {len(flights)} flights found | "
                f"Cheapest: {flights[0].get('currency', 'USD')} {flights[0].get('value', 0)} | "
                f"Avg: {flights[0].get('currency', 'USD')} {sum(f.get('value', 0) for f in flights[:5])//5}"
            )
            
            error_msg = results_text + stats_text
            
            # Create keyboard with load more
            keyboard = []
            
            if len(flights) > 3:
                keyboard.append([
                    InlineKeyboardButton("📥 Load 3 More", callback_data=f"load_more:flights:3"),
                    InlineKeyboardButton("💵 Sort by Price", callback_data="sort_price")
                ])
            
            keyboard.extend([
                [
                    InlineKeyboardButton("🔍 New Search", callback_data="service_flights"),
                    InlineKeyboardButton("⭐ Save Search", callback_data="save_search")
                ],
                [
                    InlineKeyboardButton("📧 Price Alert", callback_data="price_alert"),
                    InlineKeyboardButton("🏠 Main Menu", callback_data="back_main")
                ]
            ])
        
        # Send message
        target = msg if update.message else query
        await target.edit_text(
            error_msg, 
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard) if 'keyboard' in locals() else None,
            disable_web_page_preview=True
        )
        
        return ConversationHandler.END
        
    except Exception as e:
        logger.error(f"Flight search error: {e}")
        
        error_msg = (
            "⚠️ **Temporary Issue**\n\n"
            "We're experiencing high demand. Please:\n"
            "1. Try again in 30 seconds\n"
            "2. Use /start to begin new search\n"
            "3. Contact support if issue persists"
        )
        
        if update.message:
            await msg.edit_text(error_msg)
        else:
            await query.edit_message_text(error_msg)
        
        return ConversationHandler.END

def format_flight_results(flights, start_num):
    """Format flight results for display"""
    if not flights:
        return "No flights found."
    
    text = f"✈️ *FOUND {len(flights)} FLIGHTS*\n\n"
    
    for i, flight in enumerate(flights, start_num):
        airline = flight.get('airline', 'Unknown')
        price = flight.get('value', 0)
        currency = flight.get('currency', 'USD')
        departure = flight.get('departure_at', '')[:16].replace('T', ' ')
        duration = flight.get('duration', 0)
        
        # Format duration
        hours = duration // 60
        mins = duration % 60
        duration_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
        
        transfers = flight.get('transfers', 0)
        transfers_str = "Direct" if transfers == 0 else f"{transfers} stop(s)"
        
        text += f"*{i}. {airline}*\n"
        text += f"   ⏰ {departure} | {duration_str}\n"
        text += f"   🔄 {transfers_str}\n"
        text += f"   💰 *{currency} {price}*\n"
        text += f"   [📱 Book Now]({flight.get('affiliate_url', '#')})\n\n"
    
    return text

# Bus handlers (similar structure)
async def bus_departure_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle bus departure city"""
    user_id = update.effective_user.id
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        if query.data == "back_main":
            return await start_callback(update, context)
    
    city_query = update.message.text
    cities = CityDatabase.search_cities(city_query)
    
    if not cities:
        await update.message.reply_text(
            "City not found. Try: Cape Town, Johannesburg, Durban, Pretoria",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="service_buses")]
            ])
        )
        return BUS_DEPARTURE
    
    # Show city options
    keyboard = []
    for city in cities[:3]:
        if city.get("bus_terminals"):
            for terminal in city["bus_terminals"][:2]:
                btn_text = f"🚌 {terminal}"
                callback_data = f"bus_depart:{city['name']}:{terminal}"
                keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback_data)])
    
    keyboard.append([InlineKeyboardButton("🔍 Search Again", callback_data="search_bus_again")])
    
    await update.message.reply_text(
        "Select departure terminal:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return BUS_DEPARTURE

async def start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Restart conversation from callback"""
    query = update.callback_query
    await query.answer()
    
    # Clear user session
    user_id = update.effective_user.id
    if user_id in user_sessions:
        user_sessions.pop(user_id)
    
    # Show main menu
    keyboard = [
        [InlineKeyboardButton("✈️ Flights", callback_data="service_flights")],
        [InlineKeyboardButton("🚌 Buses", callback_data="service_buses")],
        [InlineKeyboardButton("🏨 Hotels", callback_data="service_hotels")],
        [InlineKeyboardButton("🚢 Cruises", callback_data="service_cruises")],
    ]
    
    await query.edit_message_text(
        "🌟 *Travel Deals Bot*\n\n"
        "Book flights, buses, hotels with affiliate commissions!\n"
        "Choose a service to begin:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return MAIN_MENU

def main():
    """Start the bot"""
    if not TOKEN:
        print("❌ ERROR: TELEGRAM_BOT_TOKEN environment variable is not set!")
        print("Please set it in Render.com environment variables")
        return
    
    # Keep bot alive on free tier
    keep_alive()
    
    # Create application
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Create conversation handler for flights
    flight_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_service, pattern="^service_")],
        states={
            MAIN_MENU: [CallbackQueryHandler(handle_service)],
            FLIGHT_TYPE: [CallbackQueryHandler(flight_type_handler)],
            DEPARTURE_CITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, departure_city_handler),
                CallbackQueryHandler(departure_select_handler, pattern="^(depart_select|search_again_depart)")
            ],
            DESTINATION_CITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, destination_city_handler),
                CallbackQueryHandler(destination_select_handler, pattern="^(dest_select|search_again_dest)")
            ],
            DEPARTURE_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, departure_date_handler)],
            RETURN_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, return_date_handler)],
        },
        fallbacks=[
            CommandHandler("start", start),
            CallbackQueryHandler(start_callback, pattern="^back_main$")
        ],
        allow_reentry=True
    )
    
    # Add all handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(flight_conv)
    app.add_handler(CallbackQueryHandler(start_callback, pattern="^back_main$"))
    
    async def load_more_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Load More button clicks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(":")
    service_type = data[1]  # "flights" or "buses"
    current_offset = int(data[2])
    
    user_id = update.effective_user.id
    session = user_sessions.get(user_id, {})
    
    if service_type == "flights" and "search_results" in session:
        flights = session["search_results"]
        new_offset = current_offset + 3
        
        if new_offset >= len(flights):
            await query.answer("No more flights to show", show_alert=True)
            return
        
        # Show next 3 flights
        next_flights = flights[new_offset:new_offset + 3]
        results_text = format_flight_results(next_flights, new_offset + 1)
        
        # Update keyboard
        keyboard = []
        has_more = len(flights) > new_offset + 3
        
        if has_more:
            keyboard.append([
                InlineKeyboardButton("📥 Load 3 More", callback_data=f"load_more:flights:{new_offset}"),
                InlineKeyboardButton("🔼 Back to Top", callback_data="show_first_results")
            ])
        else:
            keyboard.append([
                InlineKeyboardButton("🔼 Back to Top", callback_data="show_first_results")
            ])
        
        keyboard.extend([
            [
                InlineKeyboardButton("🔍 New Search", callback_data="service_flights"),
                InlineKeyboardButton("💳 Book Now", callback_data="show_booking")
            ],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="back_main")]
        ])
        
        await query.edit_message_text(
            results_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True
        )
        
    # Add help command
    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "Use /start to begin booking\n\n"
            "For support, contact @yourusername",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🚀 Start Booking", callback_data="back_main")]
            ])
        )
    
    app.add_handler(CommandHandler("help", help_command))
    
    # Start bot
    print("🤖 Travel Bot is starting...")
    print("✅ Bot is ready! Use /start in Telegram")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
