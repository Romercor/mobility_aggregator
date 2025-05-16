from typing import List
from providers.base import BaseProvider
from api.models import BikeItem

class NextBikeProvider(BaseProvider):
    """Provider for NextBike bike-sharing data"""
    
    def __init__(self):
        super().__init__()
        self.provider_name = "nextbike"
        self.base_url = "https://api.nextbike.net/maps/nextbike-live.json"
    
    async def get_vehicles(self, lat: float, lon: float, radius: float = 500, limit: int = 5) -> List[BikeItem]:
        """
        Get closest NextBike bikes within radius
        
        Args:
            lat: Latitude of center point
            lon: Longitude of center point
            radius: Search radius in meters
            limit: Maximum number of bikes to return
            
        Returns:
            List of closest bike items
        """
        try:
            # Request to NextBike API with coordinates and distance
            params = {
                "lat": lat,
                "lng": lon,
                "distance": radius
            }
            
            response = await self.client.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Parse response
            all_bikes = []
            
            # Process NextBike response structure
            if "countries" in data:
                for country in data["countries"]:
                    if "cities" in country:
                        for city in country["cities"]:
                            if "places" in city:
                                for place in city["places"]:
                                    # Skip places with no available bikes
                                    if not place.get("bikes_available_to_rent", 0) > 0:
                                        continue
                                    
                                    place_lat = float(place.get("lat", 0))
                                    place_lon = float(place.get("lng", 0))
                                    
                                    # Get distance directly from API response
                                    distance = place.get("dist", 0)
                                    
                                    # Get bike list
                                    if "bike_list" in place and place["bike_list"]:
                                        for bike in place["bike_list"]:
                                            # Check if bike is active and available
                                            if not bike.get("active", False) or bike.get("state") != "ok":
                                                continue
                                            
                                            # Create bike item
                                            bike_item = BikeItem(
                                                provider=self.provider_name,
                                                lat=place_lat,
                                                lon=place_lon,
                                                vehicle_id=str(bike.get("number", "")),
                                                distance=distance
                                            )
                                            all_bikes.append(bike_item)
            
            # Sort bikes by distance and return the nearest ones
            all_bikes.sort(key=lambda x: x.distance)
            return all_bikes[:limit]
            
        except Exception as e:
            print(f"Error fetching NextBike data: {str(e)}")
            import traceback
            traceback.print_exc()
            return []