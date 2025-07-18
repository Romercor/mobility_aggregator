from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional, Dict, Any, List
import datetime
import httpx
from api.models import RouteResponse, PrettyRouteResponse, BikeResponse, NearestStationResponse
from providers.RoomSchedule import get_room_schedule
from providers.bvg import BvgProvider
from providers.nextbike import NextBikeProvider
from api.models import MenuResponse, WeeklyMenu
from providers.mensa import MensaProvider
from api.models import WeatherResponse
from providers.weather import WeatherProvider
from utils.cache import api_cache, transport_cache, get_all_cache_stats, cleanup_all_caches
from api.models import RoomEvent
from providers.moses import StudentScheduleProvider
from api.models import StudentLecture, StudentScheduleResponse
from utils.api_checker import get_api_status
try:
    from database.service import DatabaseService
    from database.connection import check_database_health, db_manager
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    
router = APIRouter()
@router.get("/health")
async def health_check():
    """Health check using cached API status"""
    status = "ok"
    checks = []
    
    # Check cache
    try:
        await api_cache.set("health_test", True)
        await api_cache.get("health_test")
        checks.append("cache: ✓")
    except:
        checks.append("cache: ✗")
        status = "degraded"
    
    # Get last known API status (no HTTP calls!)
    try:
        api_status = await get_api_status()
        
        # Show current active APIs
        checks.append(f"stations: {api_status['stations_api']['provider']}")
        checks.append(f"journeys: {api_status['journeys_api']['provider']}")
        
        # Check if last check was recent
        last_check = datetime.datetime.fromisoformat(api_status['last_check'])
        age_minutes = (datetime.datetime.now() - last_check).total_seconds() / 60
        
        if age_minutes > 10:
            status = "degraded"
            checks.append(f"last_check: {int(age_minutes)}min ago")
        else:
            checks.append(f"last_check: {int(age_minutes)}min ago")
    except:
        checks.append("api_status: ✗")
        status = "degraded"
    
    # Check NextBike
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.head("https://api.nextbike.net/maps/nextbike-live.json")
            if r.status_code < 500:
                checks.append("bikes: ✓")
            else:
                checks.append("bikes: ✗")
    except:
        checks.append("bikes: ✗")
    
    # Check OpenWeatherMap
    try:
        import os
        api_key = os.getenv("OPENWEATHER_API_KEY")
        if api_key:
            async with httpx.AsyncClient(timeout=3.0) as client:
                # Test with TU Berlin coordinates
                params = {
                    "lat": 52.51254994596774,
                    "lon": 13.326949151892109,
                    "appid": api_key,
                    "units": "metric"
                }
                r = await client.get("https://api.openweathermap.org/data/2.5/weather", params=params)
                if r.status_code == 200:
                    data = r.json()
                    if "main" in data and "temp" in data["main"]:
                        checks.append("weather: ✓")
                    else:
                        checks.append("weather: ✗")
                else:
                    checks.append("weather: ✗")
        else:
            checks.append("weather: no-key")
    except:
        checks.append("weather: ✗")
    
    return {
        "status": status,
        "checks": checks
    }

@router.get("/database/health")
async def get_database_health():
    try:
        from database.connection import check_database_health
        return await check_database_health()
    except:
        return {"status": "unavailable"}
@router.get("/raw-routes")
async def get_routes(
    from_lat: float = Query(..., description="Starting point latitude"),
    from_lon: float = Query(..., description="Starting point longitude"),
    to_lat: float = Query(..., description="Destination latitude"),
    to_lon: float = Query(..., description="Destination longitude"),
    departure: Optional[str] = Query(None, description="Departure time in ISO format (e.g. 2025-05-04T21:41:00+02:00)"),
    results: int = Query(1, description="Maximum number of route options", ge=1, le=5),
    stopovers: bool = Query(False, description="Fetch & parse stopovers on the way"),
    polylines: bool = Query(False, description="Include route geometry")
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
        
        # Get route data
        async with BvgProvider() as bvg_provider:
            routes_data = await bvg_provider.get_routes(
                from_lat=from_lat,
                from_lon=from_lon,
                to_lat=to_lat,
                to_lon=to_lon,
                departure_time=departure_time,
                max_results=results,
                include_stopovers=stopovers,
                polylines=polylines
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
    stopovers: bool = Query(False, description="Fetch & parse stopovers on the way"),
    polylines: bool = Query(False, description="Include route geometry") 
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
        polylines: Include route geometry in results
    
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
        
        # Try to get from unified cache
        cache_key = f"parsed_routes:{from_lat:.6f}:{from_lon:.6f}:{to_lat:.6f}:{to_lon:.6f}:{departure}:{results}:{stopovers}:{polylines}"
        cached_result = await api_cache.get(cache_key)
        if cached_result:
            try:
                # Convert back to RouteResponse object
                return RouteResponse(**cached_result)
            except Exception as e:
                print(f"Error deserializing cached routes: {str(e)}")
                # If deserialization fails, proceed to fetch fresh data
        
        # Get parsed route data
        async with BvgProvider() as bvg_provider:
            routes_data = await bvg_provider.get_parsed_routes(
                from_lat=from_lat,
                from_lon=from_lon,
                to_lat=to_lat,
                to_lon=to_lon,
                departure_time=departure_time,
                max_results=results,
                include_stopovers=stopovers,
                polylines=polylines
            )
        
        # Cache the results as serializable data
        try:
            await api_cache.set(cache_key, routes_data.model_dump())
        except Exception as e:
            print(f"Error caching routes: {str(e)}")
            # Continue even if caching fails
        
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
        
        # Try to get from unified cache
        cache_key = f"pretty_routes:{from_lat:.6f}:{from_lon:.6f}:{to_lat:.6f}:{to_lon:.6f}:{departure}:{results}:{stopovers}"
        cached_result = await api_cache.get(cache_key)
        if cached_result:
            try:
                # Convert back to PrettyRouteResponse object
                return PrettyRouteResponse(**cached_result)
            except Exception as e:
                print(f"Error deserializing cached pretty routes: {str(e)}")
                # If deserialization fails, proceed to fetch fresh data
        
        # Get pretty route data
        async with BvgProvider() as bvg_provider:
            routes_data = await bvg_provider.get_pretty_routes(
                from_lat=from_lat,
                from_lon=from_lon,
                to_lat=to_lat,
                to_lon=to_lon,
                departure_time=departure_time,
                max_results=results,
                include_stopovers=stopovers
            )
        
        # Cache the results as serializable data
        try:
            await api_cache.set(cache_key, routes_data.model_dump())
        except Exception as e:
            print(f"Error caching pretty routes: {str(e)}")
            # Continue even if caching fails
        
        return routes_data
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching routes: {str(e)}")

@router.get("/bikes/nearby", response_model=BikeResponse)
async def get_nearby_bikes(
    lat: Optional[float] = Query(None, description="Latitude"),
    lon: Optional[float] = Query(None, description="Longitude"),
    coords: Optional[str] = Query(None, description="Coordinates in format 'lat,lon'"),
    radius: float = Query(500, description="Search radius in meters", ge=10, le=2000),
    limit: int = Query(5, description="Maximum number of bikes to return", ge=1, le=20)
):
    """
    Get nearby bikes from various providers
    
    Args:
        lat: Latitude (alternative to coords)
        lon: Longitude (alternative to coords)
        coords: Coordinates in format 'lat,lon'
        radius: Search radius in meters (default: 500m, max: 2000m)
        limit: Maximum number of bikes to return (default: 5, max: 20)
        
    Returns:
        List of nearby available bikes
    """
    try:
        # Parse coordinates from combined format if provided
        if coords:
            try:
                lat, lon = map(float, coords.split(','))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid 'coords' format. Use 'lat,lon' format.")
        
        # Check that coordinates are provided in one of the formats
        if lat is None or lon is None:
            raise HTTPException(
                status_code=400, 
                detail="Coordinates must be provided either as separate parameters (lat, lon) or combined (coords)"
            )
        
        # Try to get from transport cache (short TTL for dynamic data)
        cache_key = f"nearby_bikes:{lat:.6f}:{lon:.6f}:{radius}:{limit}"
        cached_result = await transport_cache.get(cache_key)
        if cached_result:
            try:
                # Convert back to BikeResponse object
                return BikeResponse(**cached_result)
            except Exception as e:
                print(f"Error deserializing cached bikes: {str(e)}")
                # If deserialization fails, proceed to fetch fresh data
        
        # Get bikes data
        async with NextBikeProvider() as nextbike_provider:
            bikes = await nextbike_provider.get_vehicles(lat=lat, lon=lon, radius=radius, limit=limit)
        
        # Cache results as serializable data
        result = BikeResponse(bikes=bikes)
        try:
            await transport_cache.set(cache_key, result.model_dump())
        except Exception as e:
            print(f"Error caching bikes: {str(e)}")
            # Continue even if caching fails
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching nearby bikes: {str(e)}")
    
@router.get("/nearest-stations", response_model=NearestStationResponse)
async def get_nearest_stations(
    lat: Optional[float] = Query(None, description="Latitude"),
    lon: Optional[float] = Query(None, description="Longitude"),
    coords: Optional[str] = Query(None, description="Coordinates in format 'lat,lon'"),
    results: int = Query(3, description="Maximum number of stations to return", ge=1, le=10),
    transport_type: Optional[str] = Query(None, description="Filter by transport type (bus, subway, tram, suburban)")
):
    """
    Get nearest public transport stations to a location
    """
    try:
        # Initialize message
        message = None
        
        if coords:
            try:
                parts = [part.strip() for part in coords.split(',')]
                if len(parts) != 2:
                    raise ValueError("Expected exactly two values")
                lat, lon = map(float, parts)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid 'coords' format. Use 'lat,lon' format.")
        
        if lat is None or lon is None:
            raise HTTPException(
                status_code=400, 
                detail="Coordinates must be provided either as separate parameters (lat, lon) or combined (coords)"
            )
        
        # Use BvgProvider's method which already returns PublicTransportStop objects
        async with BvgProvider() as bvg_provider:
            stations = await bvg_provider.get_nearest_stations_simple(lat, lon, results)
        
        if transport_type and stations:
            filtered_stations = [
                station for station in stations
                if station.has_transport_type(transport_type)
            ]
            if filtered_stations:
                stations = filtered_stations
            else:
                message = f"No {transport_type} stations found nearby. Showing all available stations."
        
        if stations:
            return NearestStationResponse(stops=stations, message=message)
        else:
            return NearestStationResponse(
                stops=[], 
                message="No stations found nearby"
            )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error finding stations: {str(e)}")

@router.get("/mensa/list")
async def get_available_mensas() -> List[str]:
    """
    Get list of all available mensas
    
    Returns:
        List of mensa names
    """
    try:
        async with MensaProvider() as mensa_provider:
            mensas = mensa_provider.get_available_mensas()
        return mensas
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching mensas: {str(e)}")

@router.get("/mensa/{mensa_name}/menu", response_model=MenuResponse)
async def get_mensa_menu(
    mensa_name: str,
    force_refresh: bool = Query(False, description="Force refresh cached data")
):
    """
    Get weekly menu for a specific mensa
    
    Args:
        mensa_name: Name of the mensa (hardenbergstrasse, marchstrasse, veggie)
        force_refresh: Force refresh cache
    
    Returns:
        Weekly menu for the specified mensa
    """
    try:
        async with MensaProvider() as mensa_provider:
            # Check if mensa exists
            available_mensas = mensa_provider.get_available_mensas()
            if mensa_name not in available_mensas:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Mensa '{mensa_name}' not found. Available: {available_mensas}"
                )
            
            # Get menu
            menu = await mensa_provider.get_weekly_menu(mensa_name, force_refresh)
            if not menu:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Menu not available for mensa '{mensa_name}'"
                )
            
            return MenuResponse(menu=menu)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching menu: {str(e)}")

@router.get("/mensa/all-menus")
async def get_all_menus(
    force_refresh: bool = Query(False, description="Force refresh cached data")
) -> Dict[str, WeeklyMenu]:
    """
    Get menus for all mensas
    
    Args:
        force_refresh: Force refresh cache
    
    Returns:
        Dictionary with menus for all mensas
    """
    try:
        async with MensaProvider() as mensa_provider:
            available_mensas = mensa_provider.get_available_mensas()
            
            all_menus = {}
            for mensa_name in available_mensas:
                try:
                    menu = await mensa_provider.get_weekly_menu(mensa_name, force_refresh)
                    if menu:
                        all_menus[mensa_name] = menu
                except Exception as e:
                    print(f"Failed to get menu for {mensa_name}: {str(e)}")
                    continue
            
            return all_menus
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching all menus: {str(e)}")

@router.post("/mensa/refresh")
async def refresh_all_menus():
    """
    Force refresh all mensa menus
    
    Useful for scheduled updates
    """
    try:
        async with MensaProvider() as mensa_provider:
            available_mensas = mensa_provider.get_available_mensas()
            
            updated_menus = []
            failed_menus = []
            
            for mensa_name in available_mensas:
                try:
                    menu = await mensa_provider.get_weekly_menu(mensa_name, force_refresh=True)
                    if menu:
                        updated_menus.append(mensa_name)
                    else:
                        failed_menus.append(mensa_name)
                except Exception as e:
                    print(f"Failed to refresh {mensa_name}: {str(e)}")
                    failed_menus.append(mensa_name)
        
        return {
            "status": "completed",
            "updated": len(updated_menus),
            "failed": len(failed_menus),
            "updated_mensas": updated_menus,
            "failed_mensas": failed_menus
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing menus: {str(e)}")

# ================================
# CACHE MONITORING ENDPOINTS
# ================================

@router.get("/cache/stats")
async def get_cache_statistics():
    """
    Get statistics for all cache instances
    
    Returns:
        Detailed statistics for each cache type including hit rates and memory usage
    """
    try:
        stats = get_all_cache_stats()
        total_entries = sum(cache["size"] for cache in stats.values())
        total_memory_kb = sum(cache["memory_usage_estimate_kb"] for cache in stats.values())
        
        return {
            "cache_statistics": stats,
            "summary": {
                "total_entries": total_entries,
                "total_memory_usage_kb": round(total_memory_kb, 2),
                "total_memory_usage_mb": round(total_memory_kb / 1024, 2),
                "cache_types": len(stats),
                "avg_hit_rate": round(
                    sum(cache["hit_rate_percent"] for cache in stats.values()) / len(stats), 2
                ) if stats else 0
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting cache stats: {str(e)}")

@router.post("/cache/cleanup")
async def cleanup_expired_cache():
    """
    Manually trigger cleanup of expired cache entries
    
    Returns:
        Number of entries removed from each cache
    """
    try:
        cleanup_results = await cleanup_all_caches()
        total_cleaned = sum(cleanup_results.values())
        
        return {
            "status": "completed",
            "total_entries_removed": total_cleaned,
            "cleanup_by_cache": cleanup_results,
            "message": f"Successfully cleaned {total_cleaned} expired entries"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cleaning cache: {str(e)}")

@router.delete("/cache/clear")
async def clear_all_caches_endpoint():
    """Clear all cache entries (use with caution)"""
    try:
        from utils.cache import clear_all_caches
        return await clear_all_caches()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error clearing caches: {str(e)}")
    
@router.get("/weather", response_model=WeatherResponse)
async def get_current_weather(
    lat: Optional[float] = Query(None, description="Latitude"),
    lon: Optional[float] = Query(None, description="Longitude"),
    coords: Optional[str] = Query(None, description="Coordinates in format 'lat,lon'")
):
    """
    Get current weather data (temperature, description, icon, air quality)
    
    Args:
        lat: Latitude (alternative to coords)
        lon: Longitude (alternative to coords)
        coords: Coordinates in format 'lat,lon'
        
    Returns:
        Weather data with temperature, description, icon URL, and air quality index
        
    Note:
        If no coordinates provided, returns weather for TU Berlin campus
    """
    try:
        # Parse coordinates from combined format if provided
        if coords:
            try:
                lat, lon = map(float, coords.split(','))
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid 'coords' format. Use 'lat,lon' format.")
        
        # Get weather data
        async with WeatherProvider() as weather_provider:
            weather = await weather_provider.get_weather(lat=lat, lon=lon)
        
        if not weather:
            raise HTTPException(status_code=503, detail="Weather data currently unavailable")
        
        # Determine location name
        location_name = "TU Berlin Campus"
        if lat and lon:
            if lat != WeatherProvider.DEFAULT_LAT or lon != WeatherProvider.DEFAULT_LON:
                location_name = f"Location ({lat:.4f}, {lon:.4f})"
        
        return WeatherResponse(
            weather=weather,
            location=location_name,
            coordinates={
                "lat": lat or WeatherProvider.DEFAULT_LAT,
                "lon": lon or WeatherProvider.DEFAULT_LON
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching weather: {str(e)}")


@router.get("/room_schedule", response_model=List[RoomEvent])
async def room_schedule(
    room_number: str = Query(..., description="Номер аудитории"),
    date: str = Query(..., description="Дата в формате YYYY-MM-DD")
):
    import asyncio
    loop = asyncio.get_event_loop()
    try:
        events = await loop.run_in_executor(None, get_room_schedule, room_number, date)
        return events
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/student-schedule", response_model=StudentScheduleResponse)
async def get_student_schedule(
    stupo: str = Query(..., description="Studienordnung number"),
    semester: int = Query(..., description="Current semester number", ge=1),
    filter_dates: bool = Query(True, description="Filter out past lectures")
):
    """
    Get student lecture schedule
    """
    try:
        async with StudentScheduleProvider() as provider:
            lectures, study_program_name = await provider.get_student_lectures_with_program_info(
                stupo, semester, filter_dates
            )
        
        message = None
        if not lectures:
            message = f"No available lectures found for Stupo {stupo}, Semester {semester}."
        
        return StudentScheduleResponse(
            lectures=lectures,
            study_program_name=study_program_name,
            message=message,
            total_count=len(lectures)
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching student schedule: {str(e)}")