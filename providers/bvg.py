import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime

from providers.base import BaseProvider
from api.models import Route, RouteLeg, RoutePoint, RouteResponse
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
    async def get_parsed_routes(
        self, 
        from_lat: float, 
        from_lon: float, 
        to_lat: float, 
        to_lon: float,
        departure_time: Optional[datetime] = None,
        max_results: int = 3
    ) -> RouteResponse:
        """
        Get parsed routes between two points
        
        Args:
            from_lat: Starting point latitude
            from_lon: Starting point longitude
            to_lat: Destination latitude
            to_lon: Destination longitude
            departure_time: Departure time (default: now)
            max_results: Maximum number of route options
            
        Returns:
            Structured route data
        """
        try:
            # Get raw data
            raw_data = await self.get_routes(
                from_lat=from_lat,
                from_lon=from_lon,
                to_lat=to_lat,
                to_lon=to_lon,
                departure_time=departure_time,
                max_results=max_results
            )
            
            # Parse raw data
            parsed_routes = self._parse_journeys(raw_data)
            
            return RouteResponse(routes=parsed_routes)
            
        except Exception as e:
            print(f"Error parsing route data: {str(e)}")
            import traceback
            traceback.print_exc()
            return RouteResponse(routes=[])
    
    def _parse_journeys(self, raw_data: Dict[str, Any]) -> List[Route]:
        """Parse raw journey data into Route objects"""
        if "journeys" not in raw_data:
            return []
        
        routes = []
        
        for journey in raw_data["journeys"]:
            try:
                # Parse legs
                legs = []
                total_walking_distance = 0
                
                for leg in journey.get("legs", []):
                    # Create start point
                    origin = leg.get("origin", {})
                    origin_name = origin.get("name", "Unknown")
                    if origin_name is None:
                        # Use address or coordinates if name is not available
                        origin_name = origin.get("address", f"{origin.get('latitude', 0)},{origin.get('longitude', 0)}")
                    
                    if "location" in origin and isinstance(origin["location"], dict):
                        origin_lat = origin["location"].get("latitude", 0)
                        origin_lon = origin["location"].get("longitude", 0)
                    else:
                        origin_lat = origin.get("latitude", 0)
                        origin_lon = origin.get("longitude", 0)
                    
                    start_point = RoutePoint(
                        name=origin_name,
                        latitude=origin_lat,
                        longitude=origin_lon,
                        is_stop=origin.get("type") == "stop"
                    )
                    
                    # Create end point
                    destination = leg.get("destination", {})
                    dest_name = destination.get("name", "Unknown")
                    if dest_name is None:
                        # Use address or coordinates if name is not available
                        dest_name = destination.get("address", f"{destination.get('latitude', 0)},{destination.get('longitude', 0)}")
                    
                    if "location" in destination and isinstance(destination["location"], dict):
                        dest_lat = destination["location"].get("latitude", 0)
                        dest_lon = destination["location"].get("longitude", 0)
                    else:
                        dest_lat = destination.get("latitude", 0)
                        dest_lon = destination.get("longitude", 0)
                    
                    end_point = RoutePoint(
                        name=dest_name,
                        latitude=dest_lat,
                        longitude=dest_lon,
                        is_stop=destination.get("type") == "stop"
                    )
                    
                    # Determine leg type
                    is_walking = leg.get("walking", False)
                    
                    if is_walking:
                        leg_type = "walking"
                        line = None
                        direction = None
                        distance = leg.get("distance", 0)
                        total_walking_distance += distance
                    else:
                        line_info = leg.get("line", {})
                        product = line_info.get("product", "")
                        
                        if product == "subway":
                            leg_type = "subway"
                        elif product == "suburban":
                            leg_type = "suburban"
                        elif product == "bus":
                            leg_type = "bus"
                        elif product == "tram":
                            leg_type = "tram"
                        else:
                            leg_type = "other"
                        
                        line = line_info.get("name", "")
                        direction = leg.get("direction", "")
                        distance = None
                    
                    # Calculate delay
                    delay_minutes = None
                    departure_delay = leg.get("departureDelay")
                    arrival_delay = leg.get("arrivalDelay")
                    
                    if departure_delay is not None:
                        delay_minutes = departure_delay // 60  # Convert seconds to minutes
                    elif arrival_delay is not None:
                        delay_minutes = arrival_delay // 60
                    
                    # Parse departure and arrival times
                    departure_time = datetime.fromisoformat(leg["departure"].replace('Z', '+00:00'))
                    arrival_time = datetime.fromisoformat(leg["arrival"].replace('Z', '+00:00'))
                    
                    # Get warnings
                    warnings = []
                    for remark in leg.get("remarks", []):
                        if remark.get("type") == "warning" and "summary" in remark:
                            warnings.append(remark["summary"])
                    
                    # Create leg
                    route_leg = RouteLeg(
                        start=start_point,
                        end=end_point,
                        type=leg_type,
                        line=line,
                        direction=direction,
                        departure_time=departure_time,
                        arrival_time=arrival_time,
                        delay_minutes=delay_minutes,
                        distance=distance,
                        warnings=warnings
                    )
                    
                    legs.append(route_leg)
                
                # Calculate route properties
                if legs:
                    departure_time = legs[0].departure_time
                    arrival_time = legs[-1].arrival_time
                    duration_minutes = int((arrival_time - departure_time).total_seconds() / 60)
                    
                    # Count transfers (non-walking legs minus 1)
                    non_walking_legs = [leg for leg in legs if leg.type != "walking"]
                    transfers = max(0, len(non_walking_legs) - 1)
                    
                    # Create route
                    route = Route(
                        legs=legs,
                        duration_minutes=duration_minutes,
                        transfers=transfers,
                        walking_distance=total_walking_distance,
                        departure_time=departure_time,
                        arrival_time=arrival_time
                    )
                    
                    routes.append(route)
            
            except Exception as e:
                print(f"Error parsing journey: {str(e)}")
                import traceback
                traceback.print_exc()
                continue
        
        return routes