import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from utils.geocoding import reverse_geocode
from providers.base import BaseProvider
from api.models import Route, RouteLeg, RoutePoint, RouteResponse, PrettyRouteResponse, PrettyRoute, RouteStep, Stopover
from utils.api_checker import get_current_journeys_api_base
MAX_ROUTE_DURATION_MINUTES = 1000 # change for route time restriction
class BvgProvider(BaseProvider):
    """Provider for BVG public transport data"""
    
    def __init__(self):
        super().__init__()
    
    async def get_routes(
        self,
        from_lat: float,
        from_lon: float,
        to_lat: float,
        to_lon: float,
        departure_time: Optional[datetime] = None,
        max_results: int = 2,
        include_stopovers: bool = True,
        polylines: bool = False
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
            include_stopovers: Include intermediate stops
            polylines: Include route geometry  # ← ДОБАВИТЬ В ОПИСАНИЕ
            
        Returns:
            Dictionary with raw API data
        """
        try:
            # Get dynamic URL with fallback
            try:
                base_url = await get_current_journeys_api_base()
            except Exception as e:
                print(f"Failed to get dynamic API URL: {e}, using fallback")
                base_url = "https://v6.bvg.transport.rest"

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
                "results": max_results,
                "stopovers": "true" if include_stopovers else "false",
                "polylines": "true" if polylines else "false"
            }
            
            # Add departure time if specified
            if departure_time is not None:
                params["departure"] = departure_time.strftime("%Y-%m-%dT%H:%M:%S%z")
            
            # Make request to API
            response = await self.client.get(
                f"{base_url}/journeys",
                params=params
            )
            try:
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                # Handle API errors with informative messages
                if e.response.status_code == 404:
                    try:
                        error_data = e.response.json()
                        if "hafasCode" in error_data and error_data["hafasCode"] == "H9220":
                            print('The route is too short')
                            return {
                                "info": {
                                    "type": "no_stations",
                                    "message": "No public transportation stations were found near these locations. Consider walking or using another transportation method."
                                }
                            }
                    except:
                        pass
                
                # Re-raise other errors
                raise
            
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
        max_results: int = 3,
        include_stopovers: bool = False,
        polylines: bool = False
    ) -> RouteResponse:
        """
        Get parsed routes between two points
        
        Args:
            from_lat: Starting point latitude
            from_lon: Starting point longitude
            to_lat: Destination latitude
            to_lon: Destination longitude
            departure_time: Departure time (default: now)
            include_stopovers: Include intermediate stops
            polylines: Include route geometry 
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
                max_results=max_results,
                include_stopovers=include_stopovers,
                polylines=polylines
            )
            
            # Parse raw data
            parsed_routes = await self._parse_journeys(raw_data, include_stopovers)
            
            return RouteResponse(routes=parsed_routes)
            
        except Exception as e:
            print(f"Error parsing route data: {str(e)}")
            import traceback
            traceback.print_exc()
            return RouteResponse(routes=[])
    
    async def _parse_journeys(self, raw_data: Dict[str, Any], include_stopovers: bool = False) -> List[Route]:
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
                    # Use reverse geocoding for unknown locations
                    if origin_name is None or origin_name == "Unknown":
                        origin_name = await reverse_geocode(origin_lat, origin_lon)
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
                    # Use reverse geocoding for unknown locations
                    if dest_name is None or dest_name == "Unknown":
                        dest_name = await reverse_geocode(dest_lat, dest_lon)
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
                        if distance is not None:
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
                    if leg.get("departure"):
                        departure_time = datetime.fromisoformat(leg["departure"].replace('Z', '+00:00'))
                    else:
                        departure_time = datetime.now()

                    if leg.get("arrival"):
                        arrival_time = datetime.fromisoformat(leg["arrival"].replace('Z', '+00:00'))
                    else:
                        arrival_time = departure_time + timedelta(minutes=1)
                    
                    # Get warnings
                    warnings = [
                        remark["summary"]
                        for remark in leg.get("remarks", [])
                        if remark.get("type") == "warning" and remark.get("summary")
                    ]
                    
                    # Extract platform information
                    platform = None
                    if leg.get("departurePlatform"):
                        platform = leg.get("departurePlatform")
                    elif leg.get("arrivalPlatform"):
                        platform = leg.get("arrivalPlatform")
                    # Extract polyline
                    polyline_data = leg.get("polyline") if not is_walking else None
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
                        platform=platform,
                        warnings=warnings,
                        polyline=polyline_data
                    )

                    # Process stopovers
                    stopovers = []
                    if include_stopovers and leg.get("stopovers") and leg_type != "walking":
                        for stopover in leg.get("stopovers", []):
                            if stopover.get("stop") and stopover.get("stop").get("location"):
                                stop_location = stopover["stop"]["location"]
                                    
                                # Parse arrival and departure times if available
                                arrival_time = None
                                departure_time = None
                                    
                                if stopover.get("arrival"):
                                    try:
                                        arrival_time = datetime.fromisoformat(stopover["arrival"].replace('Z', '+00:00'))
                                    except (AttributeError, ValueError):
                                        arrival_time = None
                                                                    
                                if stopover.get("departure"):
                                    try:
                                        departure_time = datetime.fromisoformat(stopover["departure"].replace('Z', '+00:00'))
                                    except (AttributeError, ValueError):
                                        departure_time = None
                                    
                                # Create stopover object
                                stopover_obj = Stopover(
                                    name=stopover["stop"].get("name", "Unknown Stop"),
                                    latitude=stop_location.get("latitude", 0),
                                    longitude=stop_location.get("longitude", 0),
                                    arrival_time=arrival_time,
                                    departure_time=departure_time,
                                    platform=stopover.get("platform")
                                )
                                stopovers.append(stopover_obj)

                    route_leg.stopovers = stopovers
                    legs.append(route_leg)
                
                # Calculate route properties
                if legs:
                    departure_time = legs[0].departure_time
                    arrival_time = legs[-1].arrival_time
                    duration_minutes = int((arrival_time - departure_time).total_seconds() / 60)
                    if duration_minutes > MAX_ROUTE_DURATION_MINUTES:
                        print(f"Skipping route with duration {duration_minutes} minutes (exceeds {MAX_ROUTE_DURATION_MINUTES} minute limit)")
                        continue
                    # Count transfers (non-walking legs minus 1)
                    non_walking_legs = [leg for leg in legs if leg.type != "walking"]
                    transfers = max(0, len(non_walking_legs) - 1)
                    # Departure time extra handling
                    for i in range(len(legs) - 1):
                        current_leg = legs[i]
                        next_leg = legs[i + 1]
                        
                        if current_leg.type != "walking" and next_leg.type == "walking":
                            time_diff = (next_leg.departure_time - current_leg.arrival_time).total_seconds() / 60
                            
                            arrival_departure_diff = (current_leg.arrival_time - current_leg.departure_time).total_seconds() / 60
                            if time_diff < 5 or arrival_departure_diff < 3:
                                realistic_arrival = next_leg.departure_time
                                
                                current_leg.arrival_time = realistic_arrival
                    
                    if legs:
                        departure_time = legs[0].departure_time
                        arrival_time = legs[-1].arrival_time
                        duration_minutes = int((arrival_time - departure_time).total_seconds() / 60)
                        if duration_minutes > MAX_ROUTE_DURATION_MINUTES:
                            print(f"Skipping route with duration {duration_minutes} minutes (exceeds {MAX_ROUTE_DURATION_MINUTES} minute limit)")
                            continue
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
    async def get_pretty_routes(
        self, 
        from_lat: float, 
        from_lon: float, 
        to_lat: float, 
        to_lon: float,
        departure_time: Optional[datetime] = None,
        max_results: int = 3,
        include_stopovers: bool = False
    ) -> PrettyRouteResponse:
        """
        Get user-friendly routes between two points
        """
        try:
            parsed_routes = await self.get_parsed_routes(
                from_lat=from_lat,
                from_lon=from_lon,
                to_lat=to_lat,
                to_lon=to_lon,
                departure_time=departure_time,
                max_results=max_results,
                include_stopovers=include_stopovers
            )
            
            pretty_routes = []
            
            for route in parsed_routes.routes:
                # Generate steps
                steps = []
                alerts = []
                
                for leg in route.legs:
                    # Collect alerts/warnings
                    for warning in leg.warnings:
                        if warning not in alerts:
                            alerts.append(warning)
                    
                    # Create step
                    departure_time = leg.departure_time.replace(tzinfo=None)
                    arrival_time = leg.arrival_time.replace(tzinfo=None)
                    duration_min = int((arrival_time - departure_time).total_seconds() / 60)
                    
                    if leg.type == "walking":
                        steps.append(RouteStep(
                            type="walking",
                            instruction=f"Walk to {leg.end.name}",
                            duration=f"{duration_min} min",
                            distance=f"{leg.distance}m" if leg.distance else None,
                            icon="walking"
                        ))
                    else:
                        # Generate information about all stops
                        stop_info = ""
                        if include_stopovers and leg.stopovers and len(leg.stopovers) > 0:
                            # Collect stop names with arrival times
                            stop_list = []
                            for stopover in leg.stopovers:
                                if stopover.arrival_time:
                                    stop_time = stopover.arrival_time.strftime("%H:%M")
                                    stop_list.append(f"{stopover.name} ({stop_time})")
                                else:
                                    stop_list.append(stopover.name)
                            
                            # Add stops information to the instruction
                            if stop_list:
                                stop_info = "\nStops: " + " → ".join(stop_list)
                        
                        # Create full instruction with main route and stops
                        instruction = f"Take {leg.line} towards {leg.direction}"
                        if stop_info:
                            instruction += stop_info
                        
                        steps.append(RouteStep(
                            type=leg.type,
                            instruction=instruction,
                            duration=f"{duration_min} min",
                            platform=leg.platform,
                            icon=leg.type
                        ))
                
                # Generate summary
                summary_parts = []
                for leg in route.legs:
                    departure_time = leg.departure_time.replace(tzinfo=None)
                    arrival_time = leg.arrival_time.replace(tzinfo=None)
                    duration_min = int((arrival_time - departure_time).total_seconds() / 60)
                    if leg.type == "walking":
                        summary_parts.append(f"Walk {duration_min} min")
                    else:
                        summary_parts.append(f"{leg.line} ({duration_min} min)")
                
                summary = " → ".join(summary_parts)
                
                # Calculate walking time
                walking_time = 0
                for leg in route.legs:
                    if leg.type == "walking":
                        walking_time += int((leg.arrival_time - leg.departure_time).total_seconds() / 60)
                
                # Create pretty route
                pretty_route = PrettyRoute(
                    summary=summary,
                    steps=steps,
                    alerts=alerts,
                    departure=route.departure_time.strftime("%H:%M"),
                    arrival=route.arrival_time.strftime("%H:%M"),
                    total_duration=f"{route.duration_minutes} minutes",
                    transfers=route.transfers,
                    walking_distance=f"{route.walking_distance}m",
                    walking_time=f"{walking_time} min"
                )
                
                pretty_routes.append(pretty_route)
            
            return PrettyRouteResponse(routes=pretty_routes)
            
        except Exception as e:
            print(f"Error creating pretty routes: {str(e)}")
            import traceback
            traceback.print_exc()
            return PrettyRouteResponse(routes=[])
    async def get_nearest_stations_simple(self, lat: float, lon: float, max_results: int = 3):
        """Wrapper for station finder using existing client"""
        from utils.station_finder import find_nearest_stations
        return await find_nearest_stations(lat, lon, max_results, self.client)
