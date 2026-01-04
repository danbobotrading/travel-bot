# City and airport data
class CityDatabase:
    """Database of cities for South Africa and bordering countries"""
    
    CITIES = [
        {
            "name": "Cape Town",
            "country": "South Africa",
            "airports": [
                {"code": "CPT", "name": "Cape Town International", "type": "international"},
                {"code": "HLE", "name": "Cape Town Heliport", "type": "domestic"}
            ],
            "bus_terminals": ["Cape Town Bus Terminal", "Bellville Station"]
        },
        {
            "name": "Johannesburg",
            "country": "South Africa",
            "airports": [
                {"code": "JNB", "name": "O.R. Tambo International", "type": "international"},
                {"code": "HLA", "name": "Lanseria International", "type": "international"}
            ],
            "bus_terminals": ["Park Station", "Rosebank Station", "Sandton Station"]
        },
        {
            "name": "Durban",
            "country": "South Africa",
            "airports": [
                {"code": "DUR", "name": "King Shaka International", "type": "international"}
            ],
            "bus_terminals": ["Durban Bus Station", "Berea Station"]
        },
        {
            "name": "Pretoria",
            "country": "South Africa",
            "airports": [],
            "bus_terminals": ["Pretoria Station", "Hatfield Station"]
        },
        {
            "name": "Port Elizabeth",
            "country": "South Africa",
            "airports": [
                {"code": "PLZ", "name": "Chief Dawid Stuurman International", "type": "international"}
            ],
            "bus_terminals": ["Gqeberha Bus Terminal"]
        },
        {
            "name": "Bloemfontein",
            "country": "South Africa",
            "airports": [
                {"code": "BFN", "name": "Bram Fischer International", "type": "international"}
            ],
            "bus_terminals": ["Bloemfontein Terminal"]
        },
        {
            "name": "Windhoek",
            "country": "Namibia",
            "airports": [
                {"code": "WDH", "name": "Hosea Kutako International", "type": "international"}
            ],
            "bus_terminals": ["Windhoek Bus Terminal"]
        },
        {
            "name": "Gaborone",
            "country": "Botswana",
            "airports": [
                {"code": "GBE", "name": "Sir Seretse Khama International", "type": "international"}
            ],
            "bus_terminals": ["Gaborone Bus Rank"]
        },
        {
            "name": "Maputo",
            "country": "Mozambique",
            "airports": [
                {"code": "MPM", "name": "Maputo International", "type": "international"}
            ],
            "bus_terminals": ["Maputo Bus Station"]
        }
    ]
    
    @classmethod
    def search_cities(cls, query):
        """Search cities by name or airport code"""
        query = query.lower().strip()
        results = []
        
        for city in cls.CITIES:
            # Match city name
            if query in city["name"].lower():
                results.append(city)
                continue
            
            # Match country
            if query in city["country"].lower():
                results.append(city)
                continue
            
            # Match airport codes
            for airport in city["airports"]:
                if query == airport["code"].lower():
                    results.append(city)
                    break
                
                if query in airport["name"].lower():
                    results.append(city)
                    break
        
        return results[:5]  # Return max 5 results
