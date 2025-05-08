import httpx
import asyncio
import json
import math
from typing import Dict, Any, Optional

# For caching results
geocode_cache = {}
# List of streets that should never appear in results for TU Berlin campus
DISALLOWED_STREETS = [
    "tauentzienstraße", 
    "a103"
]
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

async def reverse_geocode(lat: float, lon: float) -> str:
    """Get a meaningful location name from coordinates using full precision"""
    
    # Generate cache key with full precision
    cache_key = f"{lat},{lon}"
    if cache_key in geocode_cache:
        return geocode_cache[cache_key]
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Pass the coordinates directly as floats to avoid any string formatting issues
            response = await client.get(
                "https://nominatim.openstreetmap.org/reverse",
                params={
                    "lat": lat,  # Use full precision
                    "lon": lon,  # Use full precision
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
                
                # Print the raw data for debugging
                print("Raw geocoding response:")
                print(json.dumps(data, indent=2))
                
                # Get coordinates from the result
                result_lat = float(data.get("lat", 0))
                result_lon = float(data.get("lon", 0))
                
                # Calculate the distance between input and result coordinates
                distance = haversine_distance(lat, lon, result_lat, result_lon)
                
                # Maximum acceptable distance (meters)
                MAX_DISTANCE = 150
                
                # Log the coordinate comparison
                input_coords = f"Input: ({lat}, {lon})"
                result_coords = f"Result: ({result_lat}, {result_lon})"
                distance_info = f"Distance: {distance:.2f} meters (Max allowed: {MAX_DISTANCE} meters)"
                print(f"Coordinate comparison:\n{input_coords}\n{result_coords}\n{distance_info}")
                
                # Check if the result is too far from the input coordinates
                if distance > MAX_DISTANCE:
                    print(f"WARNING: Result coordinates too far from input ({distance:.2f}m > {MAX_DISTANCE}m)")
                    return f"TU Berlin Campus ({lat:.5f}, {lon:.5f})"

                # Check for disallowed streets in address
                if "address" in data and "road" in data["address"] and data["address"]["road"]:
                    road = data["address"]["road"].lower()
                    if any(street in road for street in DISALLOWED_STREETS):
                        print(f"WARNING: Disallowed street detected: {data['address']['road']}")
                        return f"TU Berlin Campus ({lat:.5f}, {lon:.5f})"
                
                location_name = get_best_location_name(data)
                
                # Final check to ensure no disallowed streets in the result
                if location_name and any(street in location_name.lower() for street in DISALLOWED_STREETS):
                    print(f"WARNING: Disallowed street in final location name: {location_name}")
                    return f"TU Berlin Campus ({lat:.5f}, {lon:.5f})"
                
                geocode_cache[cache_key] = location_name
                return location_name
            
            return f"Location ({lat}, {lon})"
            
    except Exception as e:
        print(f"Geocoding error: {str(e)}")
        return f"Location ({lat}, {lon})"

def get_best_location_name(data: Dict[str, Any]) -> str:
    """Extract the most useful location name from geocoding result"""
    
    address = data.get("address", {})
    
    # TU Berlin campus area check - if we're in this bounding box, be more strict
    lat = float(data.get("lat", 0))
    lon = float(data.get("lon", 0))
    
    # TU Berlin main campus approximate bounds
    in_tu_campus = (
        52.508 <= lat <= 52.520 and
        13.315 <= lon <= 13.335      
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

async def main():
    while True:
        try:
            # Get input from user
            print("\nEnter latitude and longitude (or 'exit' to quit)")
            user_input = input("> ")
            
            if user_input.lower() == 'exit':
                break
            
            # Parse input
            coordinates = user_input.split(',')
            if len(coordinates) != 2:
                print("Please enter coordinates in format: latitude,longitude")
                continue
            
            try:
                lat = float(coordinates[0].strip())
                lon = float(coordinates[1].strip())
            except ValueError:
                print("Invalid coordinates. Please enter numbers only.")
                continue
            
            # Get and display the address
            print(f"Looking up address for ({lat}, {lon})...")
            address = await reverse_geocode(lat, lon)
            print(f"Address: {address}")
            
        except Exception as e:
            print(f"Error: {str(e)}")

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())