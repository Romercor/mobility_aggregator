from typing import List, TypeVar
import math

T = TypeVar('T')  # Generic type for items with lat/lon attributes

def calculate_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the haversine distance between two points on earth
    
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

def filter_by_distance(items: List[T], center_lat: float, center_lon: float, radius: float) -> List[T]:
    """
    Filter items by distance from center point
    
    Args:
        items: List of items with lat/lon attributes
        center_lat: Latitude of center point
        center_lon: Longitude of center point
        radius: Maximum radius in meters
        
    Returns:
        Filtered list of items
    """
    return [
        item for item in items 
        if calculate_distance(center_lat, center_lon, item.lat, item.lon) <= radius
    ]