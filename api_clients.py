# API clients for flights/buses
import os
import aiohttp
import json

class TravelPayoutsClient:
    """Client for TravelPayouts flight API"""
    
    BASE_URL = "https://api.travelpayouts.com"
    
    @staticmethod
    def get_headers():
        token = os.environ.get("TRAVELPAYOUTS_API_TOKEN", "demo")
        return {"X-Access-Token": token}
    
    @classmethod
    async def search_flights(cls, origin, destination, departure_date, return_date=None, currency="USD", limit=10):
        """Search flights with affiliate links"""
        # For demo - return sample data
        # In production, make actual API call
        
        sample_flights = [
            {
                "airline": "SA Airlink",
                "value": 2450,
                "currency": "ZAR",
                "departure_at": f"{departure_date}T08:30:00Z",
                "duration": 125,
                "transfers": 0,
                "flight_number": "4Z101",
                "affiliate_url": f"https://www.travelstart.co.za/flights/{origin}/{destination}/{departure_date}?aff=YOURCODE"
            },
            {
                "airline": "FlySafair",
                "value": 2100,
                "currency": "ZAR",
                "departure_at": f"{departure_date}T14:15:00Z",
                "duration": 135,
                "transfers": 0,
                "flight_number": "FA201",
                "affiliate_url": f"https://www.travelstart.co.za/flights/{origin}/{destination}/{departure_date}?aff=YOURCODE"
            },
            {
                "airline": "British Airways",
                "value": 185,
                "currency": "USD",
                "departure_at": f"{departure_date}T22:45:00Z",
                "duration": 720,
                "transfers": 1,
                "flight_number": "BA123",
                "affiliate_url": f"https://www.travelstart.co.za/flights/{origin}/{destination}/{departure_date}?aff=YOURCODE"
            }
        ]
        
        # If return date provided, add return flights
        if return_date:
            sample_flights.append({
                "airline": "Emirates",
                "value": 420,
                "currency": "USD",
                "departure_at": f"{departure_date}T18:20:00Z",
                "return_at": f"{return_date}T06:45:00Z",
                "duration": 840,
                "transfers": 1,
                "flight_number": "EK765",
                "affiliate_url": f"https://www.travelstart.co.za/flights/{origin}/{destination}/{departure_date}/{return_date}?aff=YOURCODE"
            })
        
        return sample_flights[:limit]

class BusBookingClient:
    """Client for bus bookings in South Africa"""
    
    @classmethod
    async def search_buses(cls, from_city, to_city, travel_date):
        """Search bus routes"""
        # Sample bus data
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
                "affiliate_url": f"https://www.intercape.co.za/book?from={from_city}&to={to_city}&date={travel_date}&aff=YOURCODE"
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
                "affiliate_url": f"https://greyhound.co.za/booking?origin={from_city}&dest={to_city}&date={travel_date}&ref=YOURCODE"
            }
        ]
        
        return sample_buses
