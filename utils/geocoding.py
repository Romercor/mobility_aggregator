import httpx
import asyncio
import json
from typing import Dict, Any, Optional

# For caching results
geocode_cache = {}

async def reverse_geocode(lat: float, lon: float) -> str:
    """Get a meaningful location name from coordinates"""
    
    # Check cache first
    cache_key = f"{lat:.6f},{lon:.6f}"
    if cache_key in geocode_cache:
        return geocode_cache[cache_key]
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "lat": lat,
                    "lon": lon,
                    "format": "json",
                    "addressdetails": 1,
                    "accept-language": "de"
                },
                headers={
                    "User-Agent": "TU-Berlin-Campus-Router/1.0"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                location_name = get_best_location_name(data)
                geocode_cache[cache_key] = location_name
                return location_name
            
            return f"Location ({lat:.5f}, {lon:.5f})"
            
    except Exception as e:
        print(f"Geocoding error: {str(e)}")
        return f"Location ({lat:.5f}, {lon:.5f})"

def get_best_location_name(data: Dict[str, Any]) -> str:
    """Extract the most useful location name from geocoding result"""
    
    address = data.get("address", {})
    
    # Priority 1: Named locations (buildings, POIs)
    for key in ["amenity", "building", "university", "tourism", "leisure"]:
        if key in address and address[key]:
            return address[key]
    
    # Priority 2: Street address with house number
    if "road" in address and "house_number" in address:
        return f"{address['road']} {address['house_number']}"
    
    # Priority 3: Just the street name
    if "road" in address:
        return address["road"]
    
    # Priority 4: Campus area
    for key in ["campus", "suburb", "neighbourhood"]:
        if key in address and address[key]:
            return address[key]
    
    # Priority 5: Use display name (first part only)
    if "display_name" in data:
        parts = data["display_name"].split(',')
        return parts[0].strip()
    
    # Ultimate fallback
    lat = data.get("lat", "0")
    lon = data.get("lon", "0")
    return f"Location ({lat}, {lon})"