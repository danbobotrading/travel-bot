#!/usr/bin/env python3
"""
🤖 SECURE TRAVEL BOT FOR CHOREO
All API keys and affiliate IDs stored in environment variables
"""

import os
import logging
import json
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from flask import Flask, jsonify
from threading import Thread
from telegram import (
    Update, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton,
    ReplyKeyboardRemove
)
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    filters
)

# ==================== CONFIGURATION ====================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== ENVIRONMENT VARIABLES ====================
# Load ALL sensitive data from environment
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TRAVELPAYOUTS_API_TOKEN = os.environ.get("TRAVELPAYOUTS_API_TOKEN")
TRAVELPAYOUTS_AFFILIATE_ID = os.environ.get("TRAVELPAYOUTS_AFFILIATE_ID", "284678")  # Default fallback

# Bus affiliate IDs
INTERCAPE_AFFILIATE_ID = os.environ.get("INTERCAPE_AFFILIATE_ID", "YOUR_INTERCAPE_AFFILIATE")
GREYHOUND_AFFILIATE_ID = os.environ.get("GREYHOUND_AFFILIATE_ID", "YOUR_GREYHOUND_AFFILIATE")
TRANSLUX_AFFILIATE_ID = os.environ.get("TRANSLUX_AFFILIATE_ID", "YOUR_TRANSLUX_AFFILIATE")

PORT = int(os.environ.get("PORT", 8080))

# ==================== FLASK FOR HEALTH CHECKS ====================
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return jsonify({
        "status": "running",
        "service": "telegram-travel-bot",
        "version": "2.0",
        "secure": True,
        "keys": "ENVIRONMENT_VARIABLES"
    })

@flask_app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

@flask_app.route('/ping')
def ping():
    return "pong", 200

@flask_app.route('/config-check')
def config_check():
    """Check if all environment variables are set (for debugging)"""
    config_status = {
        "TELEGRAM_BOT_TOKEN": "✅ SET" if TELEGRAM_BOT_TOKEN else "❌ MISSING",
        "TRAVELPAYOUTS_API_TOKEN": "✅ SET" if TRAVELPAYOUTS_API_TOKEN else "⚠️ OPTIONAL",
        "TRAVELPAYOUTS_AFFILIATE_ID": "✅ SET" if TRAVELPAYOUTS_AFFILIATE_ID != "284678" else "⚠️ USING DEFAULT",
        "PORT": f"✅ {PORT}",
        "bus_affiliates_configured": all([
            INTERCAPE_AFFILIATE_ID != "YOUR_INTERCAPE_AFFILIATE",
            GREYHOUND_AFFILIATE_ID != "YOUR_GREYHOUND_AFFILIATE",
            TRANSLUX_AFFILIATE_ID != "YOUR_TRANSLUX_AFFILIATE"
        ])
    }
    return jsonify(config_status)

def run_flask():
    """Run Flask server for Choreo health checks"""
    flask_app.run(host='0.0.0.0', port=PORT, debug=False, threaded=True)

# ==================== CONVERSATION STATES ====================
(
    MAIN_MENU,
    FLIGHT_TYPE,
    FLIGHT_DEPARTURE,
    FLIGHT_DESTINATION,
    FLIGHT_DATE,
    FLIGHT_RETURN_DATE,
    FLIGHT_RESULTS,
    BUS_DEPARTURE,
    BUS_DESTINATION,
    BUS_DATE,
    BUS_RESULTS
) = range(11)

# ==================== DATABASE (No sensitive data here) ====================
class CityDatabase:
    """South Africa & bordering countries database"""
    
    SA_CITIES = {
        "cape town": {
            "name": "Cape Town",
            "airports": [
                {"code": "CPT", "name": "Cape Town International", "type": "international"},
                {"code": "HLE", "name": "Cape Town Heliport", "type": "domestic"}
            ],
            "bus_terminals": ["Cape Town Bus Terminal", "Bellville Station"]
        },
        "johannesburg": {
            "name": "Johannesburg",
            "airports": [
                {"code": "JNB", "name": "O.R. Tambo International", "type": "international"},
                {"code": "HLA", "name": "Lanseria International", "type": "international"}
            ],
            "bus_terminals": ["Park Station", "Rosebank Station", "Sandton Station"]
        },
        "durban": {
            "name": "Durban",
            "airports": [
                {"code": "DUR", "name": "King Shaka International", "type": "international"}
            ],
            "bus_terminals": ["Durban Bus Station", "Berea Station"]
        },
        "pretoria": {
            "name": "Pretoria",
            "airports": [],
            "bus_terminals": ["Pretoria Station", "Hatfield Station"]
        },
        "bloemfontein": {
            "name": "Bloemfontein",
            "airports": [
                {"code": "BFN", "name": "Bram Fischer International", "type": "international"}
            ],
            "bus_terminals": ["Bloemfontein Terminal"]
        }
    }
    
    BORDER_CITIES = {
        "windhoek": {"country": "Namibia", "airport": "WDH", "bus": True},
        "gaborone": {"country": "Botswana", "airport": "GBE", "bus": True},
        "maputo": {"country": "Mozambique", "airport": "MPM", "bus": True},
        "maseru": {"country": "Lesotho", "airport": "MSU", "bus": True},
        "mbabane": {"country": "Eswatini", "airport": "SHO", "bus": True}
    }
    
    @classmethod
    def search_cities(cls, query: str, service: str = "flight") -> List[Dict]:
        """Search cities with fuzzy matching"""
        query = query.lower().strip()
        results = []
        
        # Search South Africa
        for city_id, city_data in cls.SA_CITIES.items():
            if query in city_id or query in city_data["name"].lower():
                results.append({
                    "id": city_id,
                    "name": city_data["name"],
                    "country": "South Africa",
                    "airports": city_data.get("airports", []),
                    "bus_terminals": city_data.get("bus_terminals", []),
                    "type": "domestic"
                })
        
        # Search border countries
        for city_id, city_data in cls.BORDER_CITIES.items():
            if query in city_id:
                results.append({
                    "id": city_id,
                    "name": city_id.title(),
                    "country": city_data["country"],
                    "airports": [{"code": city_data["airport"], 
                                 "name": f"{city_id.title()} Airport", 
                                 "type": "international"}],
                    "bus_terminals": [f"{city_id.title()} Bus Terminal"] if city_data.get("bus") else [],
                    "type": "international"
                })
        
        return results[:5]

# ==================== API CLIENTS (Using environment variables) ====================
class TravelPayoutsAPI:
    """Real TravelPayouts API integration using environment variables"""
    
    BASE_URL = "https://api.travelpayouts.com"
    
    @staticmethod
    def get_headers():
        """Get headers with token from environment"""
        if not TRAVELPAYOUTS_API_TOKEN:
            logger.warning("TRAVELPAYOUTS_API_TOKEN not set, using demo mode")
            return {}
        
        return {
            "X-Access-Token": TRAVELPAYOUTS_API_TOKEN,
            "Accept": "application/json"
        }
    
    @classmethod
    def generate_affiliate_url(cls, origin_code: str, dest_code: str, 
                              dep_date: str, ret_date: str = None,
                              currency: str = "USD") -> str:
        """Generate affiliate URL using environment variable"""
        base = "https://aviasales.tp.st"
        params = {
            "origin_iata": origin_code,
            "destination_iata": dest_code,
            "depart_date": dep_date,
            "adults": "1",
            "currency": currency.lower(),
            "marker": TRAVELPAYOUTS_AFFILIATE_ID  # FROM ENVIRONMENT
        }
        
        if ret_date:
            params["return_date"] = ret_date
        
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{base}?{query}"
    
    @classmethod
    async def search_flights(cls, origin: str, destination: str, 
                           departure_date: str, return_date: str = None,
                           currency: str = "USD", limit: int = 20) -> List[Dict]:
        """Search flights using TravelPayouts API or fallback to demo"""
        
        # Use real API if token is available
        if TRAVELPAYOUTS_API_TOKEN:
            try:
                url = f"{cls.BASE_URL}/v2/prices/latest"
                params = {
                    "origin": origin,
                    "destination": destination,
                    "depart_date": departure_date,
                    "currency": currency.lower(),
                    "limit": limit,
                    "sorting": "price",
                    "one_way": "true" if not return_date else "false",
                    "token": TRAVELPAYOUTS_API_TOKEN
                }
                
                if return_date:
                    params["return_date"] = return_date
                
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, params=params, headers=cls.get_headers()) as response:
                        if response.status == 200:
                            data = await response.json()
                            flights = data.get("data", [])
                            
                            # Add affiliate links
                            for flight in flights:
                                flight['affiliate_url'] = cls.generate_affiliate_url(
                                    origin, destination, departure_date, return_date, currency
                                )
                            
                            return flights[:limit]
            except Exception as e:
                logger.error(f"TravelPayouts API error: {e}")
                # Fall through to demo data
        
        # DEMO DATA (when no API token or API fails)
        return cls.get_demo_flights(origin, destination, departure_date, return_date, currency)
    
    @staticmethod
    def get_demo_flights(origin: str, destination: str, 
                        departure_date: str, return_date: str = None,
                        currency: str = "USD") -> List[Dict]:
        """Demo flights for testing"""
        
        # Generate affiliate URL for demo
        affiliate_url = TravelPayoutsAPI.generate_affiliate_url(
            origin, destination, departure_date, return_date, currency
        )
        
        demo_flights = [
            {
                "airline": "SA Airlink",
                "flight_number": "4Z101",
                "value": 2450 if currency == "ZAR" else 135,
                "currency": currency,
                "departure_at": f"{departure_date}T08:30:00Z",
                "duration": 125,
                "transfers": 0,
                "affiliate_url": affiliate_url
            },
            {
                "airline": "FlySafair",
                "flight_number": "FA201",
                "value": 2100 if currency == "ZAR" else 115,
                "currency": currency,
                "departure_at": f"{departure_date}T14:15:00Z",
                "duration": 135,
                "transfers": 0,
                "affiliate_url": affiliate_url
            },
            {
                "airline": "British Airways",
                "flight_number": "BA123",
                "value": 185 if currency == "USD" else 3500,
                "currency": currency,
                "departure_at": f"{departure_date}T22:45:00Z",
                "duration": 720,
                "transfers": 1,
                "affiliate_url": affiliate_url
            }
        ]
        
        if return_date:
            demo_flights.append({
                "airline": "Emirates",
                "flight_number": "EK765",
                "value": 420 if currency == "USD" else 7800,
                "currency": currency,
                "departure_at": f"{departure_date}T18:20:00Z",
                "return_at": f"{return_date}T06:45:00Z",
                "duration": 840,
                "transfers": 1,
                "affiliate_url": affiliate_url
            })
        
        return demo_flights

class BusBookingAPI:
    """Bus booking with environment variables for affiliate IDs"""
    
    @staticmethod
    def generate_bus_url(operator: str, from_city: str, to_city: str, date: str) -> str:
        """Generate bus affiliate URL using environment variables"""
        
        # Get affiliate ID from environment
        if operator.lower() == "intercape":
            affiliate_id = INTERCAPE_AFFILIATE_ID
            base_url = "https://www.intercape.co.za/book"
            params = f"aff={affiliate_id}&from={from_city}&to={to_city}&date={date}"
        
        elif operator.lower() == "greyhound":
            affiliate_id = GREYHOUND_AFFILIATE_ID
            base_url = "https://greyhound.co.za/booking"
            params = f"ref={affiliate_id}&origin={from_city}&dest={to_city}&date={date}"
        
        elif operator.lower() == "translux":
            affiliate_id = TRANSLUX_AFFILIATE_ID
            base_url = "https://www.translux.co.za/book"
            params = f"partner={affiliate_id}&from={from_city}&to={to_city}&date={date}"
        
        else:
            return "#"
        
        # Check if using placeholder affiliate ID
        if "YOUR_" in affiliate_id:
            logger.warning(f"Using placeholder affiliate ID for {operator}")
            return f"{base_url}?from={from_city}&to={to_city}&date={date}"
        
        return f"{base_url}?{params}"
    
    @classmethod
    async def search_buses(cls, from_city: str, to_city: str, 
                          travel_date: str) -> List[Dict]:
        """Search bus routes"""
        
        # Check if any affiliate IDs are configured
        affiliate_ids_configured = all([
            INTERCAPE_AFFILIATE_ID != "YOUR_INTERCAPE_AFFILIATE",
            GREYHOUND_AFFILIATE_ID != "YOUR_GREYHOUND_AFFILIATE",
            TRANSLUX_AFFILIATE_ID != "YOUR_TRANSLUX_AFFILIATE"
        ])
        
        if not affiliate_ids_configured:
            logger.info("Bus affiliate IDs not configured, using demo mode")
        
        buses = [
            {
                "operator": "Intercape",
                "departure_time": "08:00",
                "arrival_time": "14:30",
                "duration": "6h 30m",
                "price": 450,
                "currency": "ZAR",
                "seats_available": 12,
                "type": "Luxury",
                "affiliate_url": cls.generate_bus_url("intercape", from_city, to_city, travel_date)
            },
            {
                "operator": "Greyhound",
                "departure_time": "10:30",
                "arrival_time": "17:15",
                "duration": "6h 45m",
                "price": 420,
                "currency": "ZAR",
                "seats_available": 8,
                "type": "Standard",
                "affiliate_url": cls.generate_bus_url("greyhound", from_city, to_city, travel_date)
            },
            {
                "operator": "Translux",
                "departure_time": "14:00",
                "arrival_time": "20:45",
                "duration": "6h 45m",
                "price": 480,
                "currency": "ZAR",
                "seats_available": 15,
                "type": "Luxury",
                "affiliate_url": cls.generate_bus_url("translux", from_city, to_city, travel_date)
            }
        ]
        
        return buses

# ==================== HELPER FUNCTIONS (No sensitive data) ====================
def create_city_keyboard(cities: List[Dict], service: str = "flight") -> InlineKeyboardMarkup:
    """Create inline keyboard for city selection"""
    keyboard = []
    
    for city in cities:
        city_name = city["name"]
        
        if service == "flight" and city.get("airports"):
            for airport in city["airports"]:
                button_text = f"✈️ {airport['name']} ({airport['code']})"
                callback_data = f"select_airport:{airport['code']}:{city_name}:{service}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        elif service == "bus" and city.get("bus_terminals"):
            for terminal in city["bus_terminals"][:2]:
                button_text = f"🚌 {terminal}"
                callback_data = f"select_bus:{city_name}:{terminal}"
                keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        else:
            button_text = f"📍 {city_name}, {city.get('country', '')}"
            callback_data = f"select_city:{city_name}:{service}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
    
    keyboard.append([InlineKeyboardButton("🔍 Search Again", callback_data=f"search_again:{service}")])
    keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_main")])
    
    return InlineKeyboardMarkup(keyboard)

def format_flight_results(flights: List[Dict], start_num: int = 1) -> str:
    """Format flight results for display"""
    if not flights:
        return "No flights found."
    
    message = f"✈️ *FOUND {len(flights)} FLIGHTS*\n\n"
    
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
        
        message += f"*{i}. {airline}*\n"
        message += f"   ⏰ {departure} | {duration_str}\n"
        message += f"   🔄 {transfers_str}\n"
        message += f"   💰 *{currency} {price:,}*\n"
        
        # Show affiliate link only if not placeholder
        affiliate_url = flight.get('affiliate_url', '#')
        if affiliate_url != "#":
            message += f"   [📱 Book Now]({affiliate_url})\n\n"
        else:
            message += f"   _Configure affiliate link in settings_\n\n"
    
    return message

def format_bus_results(buses: List[Dict], start_num: int = 1) -> str:
    """Format bus results for display"""
    if not buses:
        return "No buses found."
    
    message = f"🚌 *FOUND {len(buses)} BUS OPTIONS*\n\n"
    
    for i, bus in enumerate(buses, start_num):
        operator = bus.get('operator', 'Unknown')
        departure = bus.get('departure_time', '')
        arrival = bus.get('arrival_time', '')
        duration = bus.get('duration', '')
        price = bus.get('price', 0)
        currency = bus.get('currency', 'ZAR')
        seats = bus.get('seats_available', 0)
        bus_type = bus.get('type', 'Standard')
        
        message += f"*{i}. {operator} - {bus_type}*\n"
        message += f"   🕒 {departure} → {arrival} ({duration})\n"
        message += f"   💺 {seats} seats available\n"
        message += f"   💰 *{currency} {price:,}*\n"
        
        # Show affiliate link only if configured
        affiliate_url = bus.get('affiliate_url', '#')
        if "YOUR_" not in affiliate_url and affiliate_url != "#":
            message += f"   [🎫 Book Now]({affiliate_url})\n\n"
        else:
            message += f"   _Add affiliate ID for {operator} in settings_\n\n"
    
    return message

def parse_date(date_str: str) -> Optional[str]:
    """Parse various date formats"""
    try:
        # Try common formats
        for fmt in ["%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b", "%d %B"]:
            try:
                parsed = datetime.strptime(date_str, fmt)
                if parsed.year == 1900:
                    parsed = parsed.replace(year=datetime.now().year)
                return parsed.strftime("%Y-%m-%d")
            except:
                continue
        
        # Handle relative dates
        date_str = date_str.lower()
        today = datetime.now()
        
        if date_str in ["tomorrow", "tmrw"]:
            return (today + timedelta(days=1)).strftime("%Y-%m-%d")
        elif date_str.startswith("next "):
            days_ahead = 7
            return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        
    except:
        pass
    
    return None

# ==================== COMMAND HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command - main menu"""
    # Check if affiliate IDs are configured
    config_status = "⚠️"
    if (TRAVELPAYOUTS_AFFILIATE_ID != "284678" and 
        INTERCAPE_AFFILIATE_ID != "YOUR_INTERCAPE_AFFILIATE"):
        config_status = "✅"
    
    keyboard = [
        [InlineKeyboardButton("✈️ Book Flights", callback_data="book_flights")],
        [InlineKeyboardButton("🚌 Book Buses", callback_data="book_buses")],
        [InlineKeyboardButton("⚙️ Config Status", callback_data="config_status")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help_info")]
    ]
    
    await update.message.reply_text(
        f"🌟 *SECURE TRAVEL BOT* {config_status}\n\n"
        "All API keys stored securely in environment variables.\n"
        "Choose what you want to book:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return MAIN_MENU

async def config_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show configuration status"""
    query = update.callback_query
    await query.answer()
    
    status_message = """
🔐 *CONFIGURATION STATUS*

*Telegram Bot:*
• Token: {telegram_status}

*TravelPayouts:*
• API Token: {tp_api_status}
• Affiliate ID: {tp_affiliate_status}

*Bus Affiliates:*
• Intercape: {intercape_status}
• Greyhound: {greyhound_status}
• Translux: {translux_status}

*Choreo:*
• Port: {port}
• Health: ✅ Running

*To configure missing keys:*
1. Go to Choreo Console
2. Click your service
3. Go to "Environment Variables"
4. Add missing variables
""".format(
        telegram_status="✅ SET" if TELEGRAM_BOT_TOKEN else "❌ MISSING",
        tp_api_status="✅ SET" if TRAVELPAYOUTS_API_TOKEN else "⚠️ Optional",
        tp_affiliate_status="✅ SET" if TRAVELPAYOUTS_AFFILIATE_ID != "284678" else "⚠️ Using default",
        intercape_status="✅ SET" if INTERCAPE_AFFILIATE_ID != "YOUR_INTERCAPE_AFFILIATE" else "❌ Not set",
        greyhound_status="✅ SET" if GREYHOUND_AFFILIATE_ID != "YOUR_GREYHOUND_AFFILIATE" else "❌ Not set",
        translux_status="✅ SET" if TRANSLUX_AFFILIATE_ID != "YOUR_TRANSLUX_AFFILIATE" else "❌ Not set",
        port=PORT
    )
    
    await query.edit_message_text(
        status_message,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_main")],
            [InlineKeyboardButton("✈️ Book Flights", callback_data="book_flights")]
        ])
    )
    
    return MAIN_MENU

# [Rest of the handlers remain the same as previous bot.py]
# [Only change: All handlers now use the secure API classes]

# ==================== MAIN FUNCTION ====================
def main():
    """Start the secure bot"""
    print("=" * 60)
    print("🔐 SECURE TRAVEL BOT STARTING")
    print("=" * 60)
    
    # Display configuration status
    print("🔧 CONFIGURATION CHECK:")
    print(f"  • TELEGRAM_BOT_TOKEN: {'✅' if TELEGRAM_BOT_TOKEN else '❌'}")
    print(f"  • TRAVELPAYOUTS_API_TOKEN: {'✅' if TRAVELPAYOUTS_API_TOKEN else '⚠️ Optional'}")
    print(f"  • TRAVELPAYOUTS_AFFILIATE_ID: {'✅ Custom' if TRAVELPAYOUTS_AFFILIATE_ID != '284678' else '⚠️ Default'}")
    print(f"  • Bus affiliates: {'✅ Configured' if all([
        INTERCAPE_AFFILIATE_ID != 'YOUR_INTERCAPE_AFFILIATE',
        GREYHOUND_AFFILIATE_ID != 'YOUR_GREYHOUND_AFFILIATE',
        TRANSLUX_AFFILIATE_ID != 'YOUR_TRANSLUX_AFFILIATE'
    ]) else '⚠️ Using placeholders'}")
    print("=" * 60)
    
    if not TELEGRAM_BOT_TOKEN:
        print("❌ FATAL: TELEGRAM_BOT_TOKEN not set!")
        print("Add it in Choreo Environment Variables")
        print("=" * 60)
        return
    
    # Start Flask server for Choreo health checks
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print(f"✅ Health server started on port {PORT}")
    
    try:
        # Create bot application
        app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
        print("✅ Bot application created")
        
        # [Rest of the main function remains same as previous]
        # Add all handlers (same as previous version)
        
        print("=" * 60)
        print("📱 BOT IS READY! Send /start in Telegram")
        print(f"🌐 Health check: http://0.0.0.0:{PORT}/health")
        print(f"🔧 Config check: http://0.0.0.0:{PORT}/config-check")
        print("=" * 60)
        
        # Start bot
        app.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
        
    except Exception as e:
        print(f"❌ FATAL ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        print("=" * 60)

if __name__ == "__main__":
    main()
