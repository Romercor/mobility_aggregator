from fastapi import APIRouter, Query, HTTPException
from typing import Optional, Dict, Any
import datetime

from api.models import RouteResponse, PrettyRouteResponse
from providers.bvg import BvgProvider
#from providers.voi import VoiProvider
#from providers.tier import TierProvider
from utils.cache import get_cached_data, set_cached_data

router = APIRouter()

@router.get("/raw-routes")
async def get_routes(
    from_lat: float = Query(..., description="Starting point latitude"),
    from_lon: float = Query(..., description="Starting point longitude"),
    to_lat: float = Query(..., description="Destination latitude"),
    to_lon: float = Query(..., description="Destination longitude"),
    departure: Optional[str] = Query(None, description="Departure time in ISO format (e.g. 2025-05-04T21:41:00+02:00)"),
    results: int = Query(1, description="Maximum number of route options", ge=1, le=5),
    stopovers: bool = Query(False, description="Fetch & parse stopovers on the way")
):
    """
    Get route data from BVG API
    """
    try:
        # Parse departure time if specified
        departure_time = None
        if departure:
            try:
                departure_time = datetime.datetime.fromisoformat(departure)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid departure time format. Use ISO format (e.g. 2025-05-04T21:41:00+02:00)")
        
        # Initialize BVG provider
        bvg_provider = BvgProvider()
        
        # Get route data
        routes_data = await bvg_provider.get_routes(
            from_lat=from_lat,
            from_lon=from_lon,
            to_lat=to_lat,
            to_lon=to_lon,
            departure_time=departure_time,
            max_results=results,
            include_stopovers=stopovers
        )
        
        return routes_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching routes: {str(e)}")

@router.get("/routes", response_model=RouteResponse)
async def get_routes(
    from_lat: Optional[float] = Query(None, description="Starting point latitude"),
    from_lon: Optional[float] = Query(None, description="Starting point longitude"),
    to_lat: Optional[float] = Query(None, description="Destination latitude"),
    to_lon: Optional[float] = Query(None, description="Destination longitude"),
    from_coords: Optional[str] = Query(None, alias="from", description="Starting point coordinates 'lat,lon'"),
    to_coords: Optional[str] = Query(None, alias="to", description="Destination coordinates 'lat,lon'"),
    departure: Optional[str] = Query(None, description="Departure time in ISO format (e.g. 2025-05-05T11:09:00+02:00)"),
    results: int = Query(1, description="Maximum number of route options", ge=1, le=5),
    stopovers: bool = Query(False, description="Fetch & parse stopovers on the way")
):
    """
    Get structured route data from BVG API
    
    Args:
        from_lat: Starting point latitude (alternative to from)
        from_lon: Starting point longitude (alternative to from)
        to_lat: Destination latitude (alternative to to)
        to_lon: Destination longitude (alternative to to)
        from: Starting point coordinates in format 'lat,lon'
        to: Destination coordinates in format 'lat,lon'
        departure: Departure time in ISO format (optional, default: now)
        results: Maximum number of route options to return (default: 1, max: 5)
        stopovers: Include stopover information in results
    
    Returns:
        Structured route data
    """
    try:
        # Parse coordinates from combined format if provided
        if from_coords:
            try:
                from_lat, from_lon = map(float, from_coords.split(','))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid 'from' format. Use 'lat,lon' format.")
        
        if to_coords:
            try:
                to_lat, to_lon = map(float, to_coords.split(','))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid 'to' format. Use 'lat,lon' format.")
        
        # Check that coordinates are provided in one of the formats
        if from_lat is None or from_lon is None or to_lat is None or to_lon is None:
            raise HTTPException(
                status_code=400, 
                detail="Coordinates must be provided either as separate parameters (from_lat, from_lon, to_lat, to_lon) or combined (from, to)"
            )
        
        # Parse departure time if specified
        departure_time = None
        if departure:
            try:
                departure_time = datetime.datetime.fromisoformat(departure)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid departure time format. Use ISO format (e.g. 2025-05-05T11:09:00+02:00)")
        
        # Try to get from cache
        cache_key = f"parsed_routes:{from_lat:.6f}:{from_lon:.6f}:{to_lat:.6f}:{to_lon:.6f}:{departure}:{results}:{stopovers}"
        cached_result = await get_cached_data(cache_key)
        if cached_result:
            return cached_result
        
        # Initialize BVG provider
        bvg_provider = BvgProvider()
        
        # Get parsed route data
        routes_data = await bvg_provider.get_parsed_routes(
            from_lat=from_lat,
            from_lon=from_lon,
            to_lat=to_lat,
            to_lon=to_lon,
            departure_time=departure_time,
            max_results=results,
            include_stopovers=stopovers
        )
        
        # Cache the results
        await set_cached_data(cache_key, routes_data)
        
        return routes_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching routes: {str(e)}")
@router.get("/pretty-routes", response_model=PrettyRouteResponse)
async def get_pretty_routes(
    from_lat: Optional[float] = Query(None, description="Starting point latitude"),
    from_lon: Optional[float] = Query(None, description="Starting point longitude"),
    to_lat: Optional[float] = Query(None, description="Destination latitude"),
    to_lon: Optional[float] = Query(None, description="Destination longitude"),
    from_coords: Optional[str] = Query(None, alias="from", description="Starting point coordinates 'lat,lon'"),
    to_coords: Optional[str] = Query(None, alias="to", description="Destination coordinates 'lat,lon'"),
    departure: Optional[str] = Query(None, description="Departure time in ISO format (e.g. 2025-05-05T11:09:00+02:00)"),
    results: int = Query(1, description="Maximum number of route options", ge=1, le=5),
    stopovers: bool = Query(False, description="Fetch & parse stopovers on the way")
):
    """
    Get user-friendly route data formatted for display
    
    Args:
        from_lat: Starting point latitude (alternative to from)
        from_lon: Starting point longitude (alternative to from)
        to_lat: Destination latitude (alternative to to)
        to_lon: Destination longitude (alternative to to)
        from: Starting point coordinates in format 'lat,lon'
        to: Destination coordinates in format 'lat,lon'
        departure: Departure time in ISO format (optional, default: now)
        results: Maximum number of route options to return (default: 1, max: 5)
        stopovers: Include stopover information in results
        
    Returns:
        User-friendly route data
    """
    try:
        # Parse coordinates from combined format if provided
        if from_coords:
            try:
                from_lat, from_lon = map(float, from_coords.split(','))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid 'from' format. Use 'lat,lon' format.")
        
        if to_coords:
            try:
                to_lat, to_lon = map(float, to_coords.split(','))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid 'to' format. Use 'lat,lon' format.")
        
        # Check that coordinates are provided in one of the formats
        if from_lat is None or from_lon is None or to_lat is None or to_lon is None:
            raise HTTPException(
                status_code=400, 
                detail="Coordinates must be provided either as separate parameters (from_lat, from_lon, to_lat, to_lon) or combined (from, to)"
            )
        
        # Parse departure time if specified
        departure_time = None
        if departure:
            try:
                departure_time = datetime.datetime.fromisoformat(departure)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid departure time format. Use ISO format (e.g. 2025-05-05T11:09:00+02:00)")
        
        # Try to get from cache
        cache_key = f"pretty_routes:{from_lat:.6f}:{from_lon:.6f}:{to_lat:.6f}:{to_lon:.6f}:{departure}:{results}:{stopovers}"
        cached_result = await get_cached_data(cache_key)
        if cached_result:
            return cached_result
        
        # Initialize BVG provider
        bvg_provider = BvgProvider()
        
        # Get pretty route data
        routes_data = await bvg_provider.get_pretty_routes(
            from_lat=from_lat,
            from_lon=from_lon,
            to_lat=to_lat,
            to_lon=to_lon,
            departure_time=departure_time,
            max_results=results,
            include_stopovers=stopovers
        )
        
        # Cache the results
        await set_cached_data(cache_key, routes_data)
        
        return routes_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching routes: {str(e)}")