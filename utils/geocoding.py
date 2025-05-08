"""
Geocoding utilities for TU Berlin campus locations
"""
import httpx
import math
from typing import Dict, Any, Optional

# In-memory cache for geocoding results
_geocode_cache = {}

# List of streets that should never appear in results for TU Berlin campus
DISALLOWED_STREETS = [
    "tauentzienstraße", 
    "a103"
]

# TU Berlin campus bounds - used to validate if coordinates are within campus area
TU_CAMPUS_BOUNDS = {
    "min_lat": 52.508,
    "max_lat": 52.520,
    "min_lon": 13.315,
    "max_lon": 13.335
}

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth (in meters)
    
    Args:
        lat1: Latitude of first point
        lon1: Longitude of first point
        lat2: Latitude of second point
        lon2: Longitude of second point
        
    Returns:
        Distance in meters
    """
    # Earth radius in meters
    R = 6371000
    
    # Convert to radians
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    
    # Haversine formula
    a = math.sin(delta_phi/2) * math.sin(delta_phi/2) + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda/2) * math.sin(delta_lambda/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c

def get_best_location_name(data: Dict[str, Any]) -> str:
    """
    Extract the most useful location name from geocoding result
    
    Args:
        data: Raw geocoding response data
        
    Returns:
        User-friendly location name
    """
    address = data.get("address", {})
    
    # TU Berlin campus area check
    lat = float(data.get("lat", 0))
    lon = float(data.get("lon", 0))
    
    # Check if in TU Berlin campus bounds
    in_tu_campus = (
        TU_CAMPUS_BOUNDS["min_lat"] <= lat <= TU_CAMPUS_BOUNDS["max_lat"] and
        TU_CAMPUS_BOUNDS["min_lon"] <= lon <= TU_CAMPUS_BOUNDS["max_lon"]      
    )
    
    # Primary name sources in order of preference
    result = ""
    
    # For buildings on campus, prioritize building names
    if in_tu_campus:
        # Check for university buildings first
        for key in ["university", "building", "amenity"]:
            if key in address and address[key]:
                result = address[key]
                break
    
    # If no building found or not on campus, try landmarks
    if not result:
        for key in ["tourism", "amenity", "building", "university", "leisure"]:
            if key in address and address[key]:
                result = address[key]
                break
    
    # Get street information
    street_info = ""
    if "road" in address:
        street_info = address["road"]
        if "house_number" in address:
            street_info += f" {address['house_number']}"
    
    # Format the final result
    if result and street_info:
        return f"{result} ({street_info})"
    elif result:
        return result
    elif street_info:
        return street_info
    
    # Ultimate fallback with original coordinates
    orig_lat = data.get("lat", "0")
    orig_lon = data.get("lon", "0") 
    return f"Location ({orig_lat}, {orig_lon})"

async def reverse_geocode(lat: float, lon: float) -> str:
    """
    Get a meaningful location name from coordinates
    
    Args:
        lat: Latitude
        lon: Longitude
        
    Returns:
        User-friendly location name
    """
    # Generate cache key with full precision
    cache_key = f"{lat},{lon}"
    if cache_key in _geocode_cache:
        return _geocode_cache[cache_key]
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Pass the coordinates directly as floats to avoid any string formatting issues
            response = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "lat": lat,
                    "lon": lon,
                    "format": "json",
                    "addressdetails": 1,
                    "accept-language": "de",
                    "zoom": 18  # Higher zoom level for more precise results
                },
                headers={
                    "User-Agent": "TU-Berlin-Campus-Router/1.0"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Get coordinates from the result
                result_lat = float(data.get("lat", 0))
                result_lon = float(data.get("lon", 0))
                
                # Calculate the distance between input and result coordinates
                distance = haversine_distance(lat, lon, result_lat, result_lon)
                
                # Maximum acceptable distance (meters)
                MAX_DISTANCE = 150
                
                # Check if the result is too far from the input coordinates
                if distance > MAX_DISTANCE:
                    return f"TU Berlin Campus ({lat:.5f}, {lon:.5f})"

                # Check for disallowed streets in address
                if "address" in data and "road" in data["address"] and data["address"]["road"]:
                    road = data["address"]["road"].lower()
                    if any(street in road for street in DISALLOWED_STREETS):
                        return f"TU Berlin Campus ({lat:.5f}, {lon:.5f})"
                
                location_name = get_best_location_name(data)
                
                # Final check to ensure no disallowed streets in the result
                if location_name and any(street in location_name.lower() for street in DISALLOWED_STREETS):
                    return f"TU Berlin Campus ({lat:.5f}, {lon:.5f})"
                
                _geocode_cache[cache_key] = location_name
                return location_name
            
            return f"Location ({lat}, {lon})"
            
    except Exception as e:
        print(f"Geocoding error: {str(e)}")
        return f"Location ({lat}, {lon})"