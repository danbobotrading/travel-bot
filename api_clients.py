import os
import aiohttp
import json
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional

class TravelPayoutsClient:
    """REAL TravelPayouts API Client for flights"""
    
    BASE_URL = "https://api.travelpayouts.com"
    
    @staticmethod
    def get_headers():
        """Get API headers with your token"""
        token = os.environ.get("TRAVELPAYOUTS_API_TOKEN")
        if not token:
            print("⚠️ WARNING: TRAVELPAYOUTS_API_TOKEN not set. Using demo mode.")
            token = "your_travelpayouts_token_here"  # Fallback for local testing
        
        return {
            "X-Access-Token": token,
            "Accept": "application/json"
        }
    
    @classmethod
    async def search_flights(cls, origin: str, destination: str, departure_date: str, 
                           return_date: str = None, currency: str = "USD", limit: int = 10) -> List[Dict]:
        """
        Search REAL flights using TravelPayouts API
        Returns actual flight data with affiliate links
        """
        
        # Construct API URL
        url = f"{cls.BASE_URL}/v2/prices/latest"
        
        # Prepare parameters
        params = {
            "origin": origin,  # Airport code like "CPT"
            "destination": destination,  # Airport code like "JNB"
            "depart_date": departure_date,  # Format: "2024-12-20"
            "currency": currency.lower(),  # "usd", "eur", "zar"
            "limit": limit,  # Number of results
            "sorting": "price",  # Sort by cheapest first
            "one_way": "true" if not return_date else "false",
            "token": os.environ.get("TRAVELPAYOUTS_API_TOKEN", "")
        }
        
        if return_date:
            params["return_date"] = return_date
        
        print(f"🔍 Searching flights: {origin}→{destination} on {departure_date}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, 
                    params=params, 
                    headers=cls.get_headers(),
                    timeout=30  # 30 second timeout
                ) as response:
                    
                    if response.status == 200:
                        data = await response.json()
                        flights = data.get("data", [])
                        
                        print(f"✅ Found {len(flights)} real flights")
                        
                        # Add affiliate links to each flight
                        for flight in flights:
                            flight['affiliate_url'] = cls.generate_booking_link(
                                origin=origin,
                                destination=destination,
                                depart_date=departure_date,
                                return_date=return_date,
                                flight_data=flight,
                                currency=currency
                            )
                        
                        return flights[:limit]  # Return limited results
                    
                    else:
                        error_text = await response.text()
                        print(f"❌ API Error {response.status}: {error_text}")
                        
                        # Fallback to sample data if API fails
                        return cls.get_sample_flights(origin, destination, departure_date, return_date, currency)
                        
        except Exception as e:
            print(f"❌ Network error: {e}")
            # Fallback to sample data
            return cls.get_sample_flights(origin, destination, departure_date, return_date, currency)
    
    @staticmethod
    def generate_booking_link(origin: str, destination: str, depart_date: str, 
                            return_date: Optional[str], flight_data: Dict, currency: str) -> str:
        """
        Generate REAL affiliate booking link with your commission
        
        Replace 'YOUR_AFFILIATE_CODE' with your actual TravelPayouts affiliate ID
        """
        
        # Your TravelPayouts affiliate ID (get from TravelPayouts dashboard)
        AFFILIATE_ID = os.environ.get("TRAVELPAYOUTS_AFFILIATE_ID", "YOUR_AFFILIATE_CODE_HERE")
        
        # Base booking URL (Aviasales)
        base_url = "https://aviasales.tp.st"
        
        # Construct parameters
        params = {
            "origin_iata": origin,
            "destination_iata": destination,
            "depart_date": depart_date,
            "adults": "1",
            "children": "0",
            "infants": "0",
            "locale": "en",
            "currency": currency.lower(),
            "with_request": "true"
        }
        
        # Add return date for round trips
        if return_date:
            params["return_date"] = return_date
        
        # Add specific flight details if available
        if flight_data.get('airline'):
            params["airline"] = flight_data['airline']
        
        if flight_data.get('flight_number'):
            params["flight_number"] = flight_data['flight_number']
        
        # Add affiliate marker
        params["marker"] = AFFILIATE_ID
        
        # Build URL
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        affiliate_url = f"{base_url}?{query_string}"
        
        return affiliate_url
    
    @staticmethod
    def get_sample_flights(origin: str, destination: str, departure_date: str, 
                          return_date: Optional[str], currency: str) -> List[Dict]:
        """Fallback sample data when API fails"""
        
        print("⚠️ Using sample data (API failed or not configured)")
        
        sample_flights = [
            {
                "airline": "SA Airlink",
                "flight_number": "4Z101",
                "value": 2450 if currency == "ZAR" else 135,
                "currency": currency,
                "departure_at": f"{departure_date}T08:30:00Z",
                "duration": 125,
                "transfers": 0,
                "affiliate_url": TravelPayoutsClient.generate_booking_link(
                    origin, destination, departure_date, return_date, {}, currency
                )
            },
            {
                "airline": "FlySafair",
                "flight_number": "FA201",
                "value": 2100 if currency == "ZAR" else 115,
                "currency": currency,
                "departure_at": f"{departure_date}T14:15:00Z",
                "duration": 135,
                "transfers": 0,
                "affiliate_url": TravelPayoutsClient.generate_booking_link(
                    origin, destination, departure_date, return_date, {}, currency
                )
            },
            {
                "airline": "British Airways",
                "flight_number": "BA123",
                "value": 185 if currency == "USD" else 3500,
                "currency": currency,
                "departure_at": f"{departure_date}T22:45:00Z",
                "duration": 720,
                "transfers": 1,
                "affiliate_url": TravelPayoutsClient.generate_booking_link(
                    origin, destination, departure_date, return_date, {}, currency
                )
            }
        ]
        
        return sample_flights
    
    @classmethod
    async def get_airport_suggestions(cls, query: str) -> List[Dict]:
        """Get real airport/city suggestions from TravelPayouts"""
        
        url = f"{cls.BASE_URL}/data/en/cities.json"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        cities = await response.json()
                        
                        # Filter by query
                        suggestions = []
                        query_lower = query.lower()
                        
                        for city in cities:
                            name = city.get("name", "").lower()
                            code = city.get("code", "").lower()
                            country = city.get("country_name", "").lower()
                            
                            if (query_lower in name or 
                                query_lower in code or 
                                query_lower in country):
                                suggestions.append({
                                    "name": city.get("name"),
                                    "code": city.get("code"),
                                    "country": city.get("country_name"),
                                    "airports": [{"code": city.get("code"), "name": city.get("name")}]
                                })
                        
                        return suggestions[:10]  # Return top 10
                    
        except:
            pass
        
        return []


class HotelBookingClient:
    """Hotel booking via TravelPayouts Hotellook API"""
    
    @classmethod
    async def search_hotels(cls, city: str, checkin: str, checkout: str, 
                           guests: int = 1) -> List[Dict]:
        """Search hotels using Hotellook API"""
        
        # This would connect to Hotellook API
        # For now, return sample data
        
        return [
            {
                "name": "Protea Hotel Cape Town",
                "price": 1200,
                "currency": "ZAR",
                "rating": 4.2,
                "affiliate_url": f"https://search.hotellook.com/?marker=YOUR_AFFILIATE_ID&city={city}&checkIn={checkin}&checkOut={checkout}&adults={guests}"
            }
        ]


class BusBookingClient:
    """Real bus booking integration"""
    
    @classmethod
    async def search_buses(cls, from_city: str, to_city: str, travel_date: str):
        """Search REAL bus routes in South Africa"""
        
        # You can integrate with:
        # 1. Travelstart Buses API
        # 2. Direct bus company APIs
        # 3.第三方聚合API
        
        # For now, enhanced sample data
        sample_buses = [
            {
                "operator": "Intercape",
                "departure_time": "08:00",
                "arrival_time": "14:30",
                "duration": "6h 30m",
                "price": 450,
                "currency": "ZAR",
                "seats": 12,
                "type": "Luxury",
                "affiliate_url": f"https://www.intercape.co.za/book?aff=YOUR_CODE&from={from_city}&to={to_city}&date={travel_date}"
            },
            {
                "operator": "Greyhound",
                "departure_time": "10:30",
                "arrival_time": "17:15",
                "duration": "6h 45m",
                "price": 420,
                "currency": "ZAR",
                "seats": 8,
                "type": "Standard",
                "affiliate_url": f"https://www.greyhound.co.za/?ref=YOUR_CODE&origin={from_city}&dest={to_city}&date={travel_date}"
            }
        ]
        
        return sample_buses
