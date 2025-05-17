# utils/station_finder.py
from typing import Optional, List, Dict, Any
import httpx
from api.models import PublicTransportStop

async def find_nearest_stations(
    lat: float, 
    lon: float, 
    max_results: int = 3,
    client: Optional[httpx.AsyncClient] = None
) -> List[PublicTransportStop]:
    """
    Find the nearest public transport stations to given coordinates
    
    Args:
        lat: Latitude
        lon: Longitude
        max_results: Maximum number of results to return
        client: Optional httpx client (if None, creates a new one)
        
    Returns:
        List of nearest public transport stops
    """
    base_url = "https://v6.bvg.transport.rest"
    close_client = False
    
    try:
        # If no client provided, create one
        if client is None:
            client = httpx.AsyncClient(timeout=10.0)
            close_client = True
        
        url = f"{base_url}/locations/nearby"
        
        params = {
            "latitude": lat,
            "longitude": lon,
            "results": max_results,
            "distance": 1000  # Maximum 1km distance
        }
        
        response = await client.get(url, params=params)
        response.raise_for_status()
        
        # Get data from response
        data = response.json()
        
        # Process and flatten stop data
        stops = []
        for stop in data:
            if stop.get("type") == "stop":
                try:
                    # Extract coordinates from the nested location object
                    location = stop.get("location", {})
                    latitude = location.get("latitude", 0)
                    longitude = location.get("longitude", 0)
                    
                    # Create a flattened stop object
                    stop_data = {
                        "type": stop.get("type", "stop"),
                        "id": stop.get("id", ""),
                        "name": stop.get("name", "Unknown"),
                        "latitude": latitude,
                        "longitude": longitude,
                        "products": stop.get("products", {}),
                        "distance": stop.get("distance", 0),
                        "station": stop.get("station"),
                        "lines": stop.get("lines", [])
                    }
                    stops.append(PublicTransportStop(**stop_data))
                except Exception as e:
                    print(f"Error processing stop data: {str(e)}")
        
        return stops
            
    except httpx.HTTPStatusError as e:
        print(f"HTTP Error: {e}")
        return []
    except httpx.RequestError as e:
        print(f"Request Error: {e}")
        return []
    except Exception as e:
        print(f"Error finding nearest stations: {str(e)}")
        return []
    
    finally:
        # Close client if we created it
        if close_client and client:
            await client.aclose()

# Cache for station search results
_station_cache: Dict[str, List[PublicTransportStop]] = {}

async def get_cached_nearest_stations(
    lat: float, 
    lon: float, 
    max_results: int = 3,
    force_refresh: bool = False
) -> List[PublicTransportStop]:
    """
    Get nearest stations with caching
    
    Args:
        lat: Latitude
        lon: Longitude
        max_results: Maximum number of results
        force_refresh: Force refresh cache
        
    Returns:
        List of nearest stations
    """
    # Use 4 decimal precision for cache key (about 11m precision)
    cache_key = f"{lat:.4f}:{lon:.4f}:{max_results}"
    
    if not force_refresh and cache_key in _station_cache:
        return _station_cache[cache_key]
    
    # Get fresh data
    stations = await find_nearest_stations(lat, lon, max_results)
    
    # Update cache
    _station_cache[cache_key] = stations
    
    return stations