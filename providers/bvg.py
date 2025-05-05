import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime

from providers.base import BaseProvider

class BvgProvider(BaseProvider):
    """Provider for BVG public transport data"""
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://v6.bvg.transport.rest"
    
    async def get_routes(
        self, 
        from_lat: float, 
        from_lon: float, 
        to_lat: float, 
        to_lon: float,
        departure_time: Optional[datetime] = None,
        max_results: int = 3
    ) -> Dict[str, Any]:
        """
        Get routes between two points using only coordinates
        
        Args:
            from_lat: Starting point latitude
            from_lon: Starting point longitude
            to_lat: Destination latitude
            to_lon: Destination longitude
            departure_time: Departure time (default: now)
            max_results: Maximum number of route options
            
        Returns:
            Dictionary with raw API data
        """
        try:
            # Prepare request parameters
            params = {
                # Starting point
                "from.latitude": from_lat,
                "from.longitude": from_lon,
                "from.address": f"{from_lat},{from_lon}",
                
                # Destination point
                "to.latitude": to_lat,
                "to.longitude": to_lon,
                "to.address": f"{to_lat},{to_lon}",
                
                # Number of results
                "results": max_results
            }
            
            # Add departure time if specified
            if departure_time is not None:
                params["departure"] = departure_time.strftime("%Y-%m-%dT%H:%M:%S%z")
            
            # Make request to API
            response = await self.client.get(
                f"{self.base_url}/journeys",
                params=params
            )
            response.raise_for_status()
            
            # Return raw data
            return response.json()
            
        except Exception as e:
            print(f"Error fetching route data: {str(e)}")
            return {"error": str(e)}