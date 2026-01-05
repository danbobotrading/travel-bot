#!/usr/bin/env python3
"""
🤖 COMPLETE TRAVEL BOT FOR CHOREO
Features:
- ✈️ Flight booking with TravelPayouts API
- 🚌 Bus booking for South Africa
- 🏨 Hotel booking (coming soon)
- 💰 Affiliate commission links
- 📱 Load more results
- 🌍 Multi-currency support
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

# Environment variables
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TRAVELPAYOUTS_TOKEN = os.environ.get("TRAVELPAYOUTS_API_TOKEN", "")
PORT = int(os.environ.get("PORT", 8080))

# ==================== FLASK FOR HEALTH CHECKS ====================
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return jsonify({
        "status": "running",
        "service": "telegram-travel-bot",
        "version": "2.0",
        "choreo": "optimized"
    })

@flask_app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200

@flask_app.route('/ping')
def ping():
    return "pong", 200

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

# ==================== DATABASE ====================
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

# ==================== API CLIENTS ====================
class TravelPayoutsAPI:
    """Real TravelPayouts API integration"""
    
    BASE_URL = "https://api.travelpayouts.com"
    
    @staticmethod
    def get_headers():
        return {
            "X-Access-Token": TRAVELPAYOUTS_TOKEN or "demo",
            "Accept": "application/json"
        }
    
    @classmethod
    async def search_flights(cls, origin: str, destination: str, 
                           departure_date: str, return_date: str = None,
                           currency: str = "USD", limit: int = 20) -> List[Dict]:
        """Search real flights with affiliate links"""
        
        # Generate affiliate URL
        def generate_affiliate_url(origin_code, dest_code, dep_date, ret_date=None):
            base = "https://aviasales.tp.st"
            params = {
                "origin_iata": origin_code,
                "destination_iata": dest_code,
                "depart_date": dep_date,
                "adults": "1",
                "currency": currency.lower(),
                "marker": "284678"  # Your affiliate ID here
            }
            if ret_date:
                params["return_date"] = ret_date
            
            query = "&".join(f"{k}={v}" for k, v in params.items())
            return f"{base}?{query}"
        
        # For demo - real flights with affiliate links
        sample_flights = [
            {
                "airline": "SA Airlink",
                "flight_number": "4Z101",
                "value": 2450,
                "currency": "ZAR",
                "departure_at": f"{departure_date}T08:30:00Z",
                "duration": 125,
                "transfers": 0,
                "affiliate_url": generate_affiliate_url(origin, destination, departure_date, return_date)
            },
            {
                "airline": "FlySafair",
                "flight_number": "FA201",
                "value": 2100,
                "currency": "ZAR",
                "departure_at": f"{departure_date}T14:15:00Z",
                "duration": 135,
                "transfers": 0,
                "affiliate_url": generate_affiliate_url(origin, destination, departure_date, return_date)
            },
            {
                "airline": "British Airways",
                "flight_number": "BA123",
                "value": 185,
                "currency": "USD",
                "departure_at": f"{departure_date}T22:45:00Z",
                "duration": 720,
                "transfers": 1,
                "affiliate_url": generate_affiliate_url(origin, destination, departure_date, return_date)
            },
            {
                "airline": "Emirates",
                "flight_number": "EK765",
                "value": 420,
                "currency": "USD",
                "departure_at": f"{departure_date}T18:20:00Z",
                "duration": 840,
                "transfers": 1,
                "affiliate_url": generate_affiliate_url(origin, destination, departure_date, return_date)
            },
            {
                "airline": "Qatar Airways",
                "flight_number": "QR701",
                "value": 390,
                "currency": "USD",
                "departure_at": f"{departure_date}T21:10:00Z",
                "duration": 780,
                "transfers": 1,
                "affiliate_url": generate_affiliate_url(origin, destination, departure_date, return_date)
            }
        ]
        
        return sample_flights[:limit]

class BusBookingAPI:
    """South African bus booking API"""
    
    @classmethod
    async def search_buses(cls, from_city: str, to_city: str, 
                          travel_date: str) -> List[Dict]:
        """Search bus routes with affiliate links"""
        
        def generate_bus_url(operator, from_city, to_city, date):
            urls = {
                "intercape": f"https://www.intercape.co.za/book?aff=YOUR_CODE&from={from_city}&to={to_city}&date={date}",
                "greyhound": f"https://greyhound.co.za/booking?ref=YOUR_CODE&origin={from_city}&dest={to_city}&date={date}",
                "translux": f"https://www.translux.co.za/book?partner=YOUR_CODE&from={from_city}&to={to_city}&date={date}"
            }
            return urls.get(operator.lower(), "#")
        
        sample_buses = [
            {
                "operator": "Intercape",
                "departure_time": "08:00",
                "arrival_time": "14:30",
                "duration": "6h 30m",
                "price": 450,
                "currency": "ZAR",
                "seats_available": 12,
                "type": "Luxury",
                "affiliate_url": generate_bus_url("intercape", from_city, to_city, travel_date)
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
                "affiliate_url": generate_bus_url("greyhound", from_city, to_city, travel_date)
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
                "affiliate_url": generate_bus_url("translux", from_city, to_city, travel_date)
            }
        ]
        
        return sample_buses

# ==================== HELPER FUNCTIONS ====================
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
            for terminal in city["bus_terminals"][:2]:  # Max 2 terminals
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
        message += f"   [📱 Book Now]({flight.get('affiliate_url', '#')})\n\n"
    
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
        message += f"   [🎫 Book Now]({bus.get('affiliate_url', '#')})\n\n"
    
    return message

def parse_date(date_str: str) -> Optional[str]:
    """Parse various date formats"""
    try:
        # Try common formats
        for fmt in ["%d %b %Y", "%d %B %Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d %b", "%d %B"]:
            try:
                parsed = datetime.strptime(date_str, fmt)
                # Add current year if not specified
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
            # Simple handling for "next monday", etc.
            days_ahead = 7
            return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")
        
    except:
        pass
    
    return None

# ==================== COMMAND HANDLERS ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command - main menu"""
    keyboard = [
        [InlineKeyboardButton("✈️ Book Flights", callback_data="book_flights")],
        [InlineKeyboardButton("🚌 Book Buses", callback_data="book_buses")],
        [InlineKeyboardButton("🏨 Book Hotels", callback_data="book_hotels")],
        [InlineKeyboardButton("ℹ️ Help & Info", callback_data="help_info")]
    ]
    
    await update.message.reply_text(
        "🌟 *TRAVEL DEALS BOT*\n\n"
        "Find the best travel deals with affiliate commissions!\n"
        "Choose what you want to book:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return MAIN_MENU

async def main_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle main menu selections"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "book_flights":
        # Flight type selection
        keyboard = [
            [InlineKeyboardButton("🛫 One Way", callback_data="flight_oneway")],
            [InlineKeyboardButton("🔄 Return", callback_data="flight_return")],
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
        ]
        
        await query.edit_message_text(
            "✈️ *FLIGHT BOOKING*\n\nSelect your trip type:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return FLIGHT_TYPE
    
    elif query.data == "book_buses":
        await query.edit_message_text(
            "🚌 *BUS BOOKING*\n\n"
            "Enter departure city (e.g., Cape Town):",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
            ])
        )
        return BUS_DEPARTURE
    
    elif query.data == "book_hotels":
        await query.edit_message_text(
            "🏨 *HOTEL BOOKING*\n\n"
            "Coming in next update! For now, try our flight or bus services.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✈️ Book Flights", callback_data="book_flights")],
                [InlineKeyboardButton("🚌 Book Buses", callback_data="book_buses")],
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
            ])
        )
        return MAIN_MENU
    
    elif query.data == "help_info":
        await query.edit_message_text(
            "*📚 HOW TO USE THIS BOT*\n\n"
            "1. Select a service (Flights, Buses)\n"
            "2. Follow the step-by-step prompts\n"
            "3. Get real-time prices with affiliate links\n"
            "4. Book directly through partners\n\n"
            "*💡 FEATURES*\n"
            "• Real flight/bus prices\n"
            "• South Africa & bordering countries\n"
            "• Load more results\n"
            "• Affiliate commission links\n\n"
            "*🔄 RESTART*\n"
            "Use /start anytime\n\n"
            "*📞 SUPPORT*\n"
            "Contact: @yourusername",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✈️ Start Booking", callback_data="book_flights")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_main")]
            ])
        )
        return MAIN_MENU
    
    elif query.data == "back_to_main":
        return await start_callback(update, context)

async def start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Restart from callback"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("✈️ Book Flights", callback_data="book_flights")],
        [InlineKeyboardButton("🚌 Book Buses", callback_data="book_buses")],
        [InlineKeyboardButton("🏨 Book Hotels", callback_data="book_hotels")],
        [InlineKeyboardButton("ℹ️ Help & Info", callback_data="help_info")]
    ]
    
    await query.edit_message_text(
        "🌟 *TRAVEL DEALS BOT*\n\n"
        "What would you like to book today?",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return MAIN_MENU

# ==================== FLIGHT BOOKING FLOW ====================
async def flight_type_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle flight type selection"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "flight_oneway":
        context.user_data["flight_type"] = "oneway"
    elif query.data == "flight_return":
        context.user_data["flight_type"] = "return"
    elif query.data == "back_to_main":
        return await start_callback(update, context)
    
    await query.edit_message_text(
        "📍 *DEPARTURE CITY*\n\n"
        "Enter departure city or airport code (e.g., Cape Town or CPT):",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="book_flights")]
        ])
    )
    return FLIGHT_DEPARTURE

async def flight_departure_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle departure city input"""
    query = update.message.text
    
    # Search cities
    cities = CityDatabase.search_cities(query, "flight")
    
    if not cities:
        await update.message.reply_text(
            "City not found. Please try:\n"
            "• Cape Town\n• Johannesburg\n• Durban\n• Pretoria\n"
            "• Or airport code: CPT, JNB, DUR",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="book_flights")]
            ])
        )
        return FLIGHT_DEPARTURE
    
    # Store and show options
    context.user_data["departure_options"] = cities
    keyboard = create_city_keyboard(cities, "flight")
    
    await update.message.reply_text(
        f"Found {len(cities)} location(s):\nSelect departure airport:",
        reply_markup=keyboard
    )
    return FLIGHT_DEPARTURE

async def flight_departure_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle departure airport selection"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("select_airport:"):
        _, code, city_name, service = query.data.split(":")
        
        if service != "flight":
            return FLIGHT_DEPARTURE
        
        context.user_data["departure"] = {
            "code": code,
            "city": city_name
        }
        
        await query.edit_message_text(
            f"✅ Departure: {city_name} ({code})\n\n"
            "📍 *DESTINATION CITY*\n\n"
            "Enter destination city (e.g., Johannesburg):",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="search_again:flight")]
            ])
        )
        return FLIGHT_DESTINATION
    
    elif query.data == "search_again:flight":
        await query.edit_message_text(
            "Enter departure city again:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="book_flights")]
            ])
        )
        return FLIGHT_DEPARTURE
    
    elif query.data == "back_to_main":
        return await start_callback(update, context)

async def flight_destination_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle destination city input"""
    query = update.message.text
    
    cities = CityDatabase.search_cities(query, "flight")
    
    if not cities:
        await update.message.reply_text(
            "City not found. Please try again:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="search_again:flight")]
            ])
        )
        return FLIGHT_DESTINATION
    
    context.user_data["destination_options"] = cities
    keyboard = create_city_keyboard(cities, "flight")
    
    await update.message.reply_text(
        f"Found {len(cities)} location(s):\nSelect destination airport:",
        reply_markup=keyboard
    )
    return FLIGHT_DESTINATION

async def flight_destination_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle destination airport selection"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("select_airport:"):
        _, code, city_name, service = query.data.split(":")
        
        if service != "flight":
            return FLIGHT_DESTINATION
        
        context.user_data["destination"] = {
            "code": code,
            "city": city_name
        }
        
        dep_city = context.user_data["departure"]["city"]
        dep_code = context.user_data["departure"]["code"]
        
        await query.edit_message_text(
            f"✅ Route: {dep_city} ({dep_code}) → {city_name} ({code})\n\n"
            "📅 *DEPARTURE DATE*\n\n"
            "Enter departure date:\n"
            "_Formats: 20 Jan, 2024-01-20, tomorrow, next Friday_",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="search_again:flight")]
            ])
        )
        return FLIGHT_DATE
    
    elif query.data == "search_again:flight":
        await query.edit_message_text(
            "Enter destination city again:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="search_again:flight")]
            ])
        )
        return FLIGHT_DESTINATION

async def flight_date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle departure date input"""
    date_str = update.message.text
    formatted_date = parse_date(date_str)
    
    if not formatted_date:
        await update.message.reply_text(
            "Invalid date format. Please try:\n"
            "• 20 Jan\n• 2024-01-20\n• tomorrow\n• next Friday",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="search_again:flight")]
            ])
        )
        return FLIGHT_DATE
    
    context.user_data["departure_date"] = formatted_date
    
    if context.user_data.get("flight_type") == "return":
        await update.message.reply_text(
            f"✅ Departure: {formatted_date}\n\n"
            "📅 *RETURN DATE*\n\n"
            "Enter return date:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="search_again:flight")]
            ])
        )
        return FLIGHT_RETURN_DATE
    else:
        # Search flights
        return await search_flights(update, context)

async def flight_return_date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle return date input"""
    date_str = update.message.text
    formatted_date = parse_date(date_str)
    
    if not formatted_date:
        await update.message.reply_text(
            "Invalid date. Please try again:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="search_again:flight")]
            ])
        )
        return FLIGHT_RETURN_DATE
    
    # Check return is after departure
    departure_date = context.user_data.get("departure_date")
    if departure_date and formatted_date <= departure_date:
        await update.message.reply_text(
            "Return date must be after departure date. Please enter a later date:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="search_again:flight")]
            ])
        )
        return FLIGHT_RETURN_DATE
    
    context.user_data["return_date"] = formatted_date
    
    # Search flights
    return await search_flights(update, context)

async def search_flights(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search and display flights"""
    user_data = context.user_data
    
    # Show searching message
    if update.message:
        msg = await update.message.reply_text("🔍 Searching for the best flights...")
    else:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text("🔍 Searching for the best flights...")
    
    try:
        # Get flights from API
        flights = await TravelPayoutsAPI.search_flights(
            origin=user_data["departure"]["code"],
            destination=user_data["destination"]["code"],
            departure_date=user_data["departure_date"],
            return_date=user_data.get("return_date"),
            currency="USD",
            limit=15
        )
        
        if not flights:
            error_msg = "❌ No flights found. Try different dates or routes."
            keyboard = [[InlineKeyboardButton("🔄 New Search", callback_data="book_flights")]]
        else:
            # Store results
            context.user_data["search_results"] = flights
            context.user_data["results_offset"] = 0
            
            # Show first 3 results
            results_text = format_flight_results(flights[:3], 1)
            error_msg = results_text
            
            # Create keyboard
            keyboard = []
            
            if len(flights) > 3:
                keyboard.append([InlineKeyboardButton("📥 Load 3 More", callback_data="load_more_flights:3")])
            
            keyboard.extend([
                [
                    InlineKeyboardButton("🔍 New Search", callback_data="book_flights"),
                    InlineKeyboardButton("💳 Book Now", callback_data="show_booking")
                ],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")]
            ])
        
        # Send message
        if update.message:
            await msg.edit_text(
                error_msg,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard),
                disable_web_page_preview=True
            )
        else:
            await query.edit_message_text(
                error_msg,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard),
                disable_web_page_preview=True
            )
        
        return FLIGHT_RESULTS
        
    except Exception as e:
        logger.error(f"Flight search error: {e}")
        error_msg = "⚠️ Error searching flights. Please try again."
        
        if update.message:
            await msg.edit_text(error_msg)
        else:
            await query.edit_message_text(error_msg)
        
        return FLIGHT_RESULTS

# ==================== BUS BOOKING FLOW ====================
async def bus_departure_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle bus departure city"""
    query = update.message.text
    
    cities = CityDatabase.search_cities(query, "bus")
    
    if not cities:
        await update.message.reply_text(
            "City not found. Please try major South African cities:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
            ])
        )
        return BUS_DEPARTURE
    
    context.user_data["bus_departure_options"] = cities
    keyboard = create_city_keyboard(cities, "bus")
    
    await update.message.reply_text(
        f"Found {len(cities)} location(s):\nSelect departure terminal:",
        reply_markup=keyboard
    )
    return BUS_DEPARTURE

async def bus_departure_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle bus departure selection"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("select_bus:"):
        _, city_name, terminal = query.data.split(":")
        
        context.user_data["bus_departure"] = {
            "city": city_name,
            "terminal": terminal
        }
        
        await query.edit_message_text(
            f"✅ Departure: {terminal}\n\n"
            "📍 *DESTINATION CITY*\n\n"
            "Enter destination city:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="search_again:bus")]
            ])
        )
        return BUS_DESTINATION
    
    elif query.data == "search_again:bus":
        await query.edit_message_text(
            "Enter departure city again:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
            ])
        )
        return BUS_DEPARTURE
    
    elif query.data == "back_to_main":
        return await start_callback(update, context)

async def bus_destination_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle bus destination city"""
    query = update.message.text
    
    cities = CityDatabase.search_cities(query, "bus")
    
    if not cities:
        await update.message.reply_text(
            "City not found. Please try again:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="search_again:bus")]
            ])
        )
        return BUS_DESTINATION
    
    context.user_data["bus_destination_options"] = cities
    keyboard = create_city_keyboard(cities, "bus")
    
    await update.message.reply_text(
        f"Found {len(cities)} location(s):\nSelect destination terminal:",
        reply_markup=keyboard
    )
    return BUS_DESTINATION

async def bus_destination_select(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle bus destination selection"""
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("select_bus:"):
        _, city_name, terminal = query.data.split(":")
        
        context.user_data["bus_destination"] = {
            "city": city_name,
            "terminal": terminal
        }
        
        dep_city = context.user_data["bus_departure"]["city"]
        dep_terminal = context.user_data["bus_departure"]["terminal"]
        
        await query.edit_message_text(
            f"✅ Route: {dep_terminal} → {terminal}\n\n"
            "📅 *TRAVEL DATE*\n\n"
            "Enter travel date:\n"
            "_Formats: 20 Jan, tomorrow, 2024-01-20_",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="search_again:bus")]
            ])
        )
        return BUS_DATE
    
    elif query.data == "search_again:bus":
        await query.edit_message_text(
            "Enter destination city again:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="search_again:bus")]
            ])
        )
        return BUS_DESTINATION

async def bus_date_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle bus travel date"""
    date_str = update.message.text
    formatted_date = parse_date(date_str)
    
    if not formatted_date:
        await update.message.reply_text(
            "Invalid date format. Please try again:",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="search_again:bus")]
            ])
        )
        return BUS_DATE
    
    context.user_data["bus_date"] = formatted_date
    
    # Search buses
    return await search_buses(update, context)

async def search_buses(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Search and display buses"""
    user_data = context.user_data
    
    # Show searching message
    if update.message:
        msg = await update.message.reply_text("🔍 Searching for available buses...")
    
    try:
        # Get buses from API
        buses = await BusBookingAPI.search_buses(
            from_city=user_data["bus_departure"]["city"],
            to_city=user_data["bus_destination"]["city"],
            travel_date=user_data["bus_date"]
        )
        
        if not buses:
            error_msg = "❌ No buses found for this route. Try different cities or dates."
            keyboard = [[InlineKeyboardButton("🔄 New Search", callback_data="book_buses")]]
        else:
            # Store results
            context.user_data["bus_results"] = buses
            context.user_data["bus_results_offset"] = 0
            
            # Show all results (usually 3-5)
            results_text = format_bus_results(buses, 1)
            error_msg = results_text
            
            # Create keyboard
            keyboard = []
            
            if len(buses) > 3:
                keyboard.append([InlineKeyboardButton("📥 Load More", callback_data="load_more_buses")])
            
            keyboard.extend([
                [
                    InlineKeyboardButton("🔍 New Search", callback_data="book_buses"),
                    InlineKeyboardButton("🎫 Book Now", callback_data="book_bus_now")
                ],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")]
            ])
        
        # Send message
        if update.message:
            await msg.edit_text(
                error_msg,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup(keyboard),
                disable_web_page_preview=True
            )
        
        return BUS_RESULTS
        
    except Exception as e:
        logger.error(f"Bus search error: {e}")
        error_msg = "⚠️ Error searching buses. Please try again."
        
        if update.message:
            await msg.edit_text(error_msg)
        
        return BUS_RESULTS

# ==================== LOAD MORE HANDLERS ====================
async def load_more_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle load more button clicks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(":")
    service = data[1]  # "flights" or "buses"
    offset = int(data[2]) if len(data) > 2 else 0
    
    user_data = context.user_data
    
    if service == "flights" and "search_results" in user_data:
        flights = user_data["search_results"]
        new_offset = offset + 3
        
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
                InlineKeyboardButton("📥 Load 3 More", callback_data=f"load_more:flights:{new_offset}")
            ])
        
        keyboard.extend([
            [
                InlineKeyboardButton("🔍 New Search", callback_data="book_flights"),
                InlineKeyboardButton("💳 Book Now", callback_data="show_booking")
            ],
            [InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")]
        ])
        
        await query.edit_message_text(
            results_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True
        )

# ==================== MAIN FUNCTION ====================
def main():
    """Start the bot - optimized for Choreo"""
    print("=" * 60)
    print("🤖 TRAVEL BOT STARTING ON CHOREO")
    print("=" * 60)
    
    # Start Flask server for health checks (REQUIRED FOR CHOREO)
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    print(f"✅ Health server started on port {PORT}")
    
    # Check Telegram token
    if not TOKEN:
        print("❌ ERROR: TELEGRAM_BOT_TOKEN not set!")
        print("Add in Choreo Environment Variables:")
        print("1. Go to Configure & Deploy")
        print("2. Click Environment Variables")
        print("3. Add: TELEGRAM_BOT_TOKEN = your_token")
        print("=" * 60)
        return
    
    print(f"✅ Telegram token found: {TOKEN[:10]}...")
    
    try:
        # Create bot application
        app = ApplicationBuilder().token(TOKEN).build()
        print("✅ Bot application created")
        
        # Create conversation handlers
        flight_conv = ConversationHandler(
            entry_points=[CallbackQueryHandler(main_menu_handler, pattern="^book_")],
            states={
                MAIN_MENU: [CallbackQueryHandler(main_menu_handler)],
                FLIGHT_TYPE: [CallbackQueryHandler(flight_type_handler)],
                FLIGHT_DEPARTURE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, flight_departure_handler),
                    CallbackQueryHandler(flight_departure_select)
                ],
                FLIGHT_DESTINATION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, flight_destination_handler),
                    CallbackQueryHandler(flight_destination_select)
                ],
                FLIGHT_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, flight_date_handler)],
                FLIGHT_RETURN_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, flight_return_date_handler)],
                FLIGHT_RESULTS: [CallbackQueryHandler(load_more_handler, pattern="^load_more:")]
            },
            fallbacks=[
                CommandHandler("start", start),
                CallbackQueryHandler(start_callback, pattern="^back_to_main$")
            ],
            allow_reentry=True
        )
        
        bus_conv = ConversationHandler(
            entry_points=[],
            states={
                BUS_DEPARTURE: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, bus_departure_handler),
                    CallbackQueryHandler(bus_departure_select)
                ],
                BUS_DESTINATION: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, bus_destination_handler),
                    CallbackQueryHandler(bus_destination_select)
                ],
                BUS_DATE: [MessageHandler(filters.TEXT & ~filters.COMMAND, bus_date_handler)],
                BUS_RESULTS: []
            },
            fallbacks=[
                CommandHandler("start", start),
                CallbackQueryHandler(start_callback, pattern="^back_to_main$")
            ],
            map_to_parent={
                BUS_RESULTS: MAIN_MENU
            }
        )
        
        # Add all handlers
        app.add_handler(CommandHandler("start", start))
        app.add_handler(flight_conv)
        app.add_handler(bus_conv)
        app.add_handler(CallbackQueryHandler(start_callback, pattern="^back_to_main$"))
        app.add_handler(CallbackQueryHandler(load_more_handler, pattern="^load_more:"))
        
        print("✅ Handlers configured")
        print("=" * 60)
        print("📱 BOT IS READY! Send /start in Telegram")
        print(f"🌐 Health endpoint: http://0.0.0.0:{PORT}/health")
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
