from fastapi import APIRouter, Query, HTTPException
from typing import Optional, Dict, Any
import datetime
from api.models import AggregatedResponse, TransportItem
from providers.bvg import BvgProvider
from providers.voi import VoiProvider
from providers.tier import TierProvider
from utils.cache import get_cached_data, set_cached_data

router = APIRouter()

@router.get("/raw-routes")
async def get_routes(
    from_lat: float = Query(..., description="Starting point latitude"),
    from_lon: float = Query(..., description="Starting point longitude"),
    to_lat: float = Query(..., description="Destination latitude"),
    to_lon: float = Query(..., description="Destination longitude"),
    departure: Optional[str] = Query(None, description="Departure time in ISO format (e.g. 2025-05-04T21:41:00+02:00)"),
    results: int = Query(1, description="Maximum number of route options", ge=1, le=5)
):
    """
    Get route data from BVG API
    """
    try:
        # Parse departure time if specified
        departure_time = None
        if departure:
            try:
                departure_time = datetime.fromisoformat(departure)
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
            max_results=results
        )
        
        return routes_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching routes: {str(e)}")