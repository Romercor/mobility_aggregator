import asyncio
import httpx
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Dict, List

# ===== API State Management =====
@dataclass
class APIState:
    stations_base: str
    stations_name: str
    journeys_base: str
    journeys_name: str
    last_check: datetime

class APIStateManager:
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._state = APIState(
                stations_base="https://v6.bvg.transport.rest",
                stations_name="bvg",
                journeys_base="https://v6.bvg.transport.rest",
                journeys_name="bvg",
                last_check=datetime.now()
            )
            self._failure_counts = {
                "bvg_stations": 0,
                "bvg_journeys": 0,
                "vbb_stations": 0,
                "vbb_journeys": 0
            }
            self._initialized = True
    
    async def get_state(self) -> APIState:
        """Thread-safe get state"""
        async with self._lock:
            return APIState(
                stations_base=self._state.stations_base,
                stations_name=self._state.stations_name,
                journeys_base=self._state.journeys_base,
                journeys_name=self._state.journeys_name,
                last_check=self._state.last_check
            )
    
    async def update_state(self, **kwargs):
        """Thread-safe update state"""
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._state, key):
                    setattr(self._state, key, value)
            self._state.last_check = datetime.now()
    
    async def handle_failure(self, api_key: str, threshold: int = 1) -> bool:
        """Handle failures with hysteresis. Returns True if should switch"""
        async with self._lock:
            self._failure_counts[api_key] += 1
            return self._failure_counts[api_key] >= threshold
    
    async def reset_failures(self, api_key: str):
        """Reset failure counter"""
        async with self._lock:
            self._failure_counts[api_key] = 0

# ===== Global instance =====
_api_manager = APIStateManager()

# ===== Test Data =====
STATION_TESTS = [
    {"latitude": 52.509037929829745, "longitude": 13.332275324649462, "results": 1},
    {"latitude": 52.50915732081264, "longitude": 13.326384039961827, "results": 1}, 
    {"latitude": 52.516949922594605, "longitude": 13.324130741250828, "results": 1}
]

ROUTE_TESTS = [
    {
        "from.latitude": 52.50718979876262, "from.longitude": 13.331650735923587,
        "from.address": "52.50718979876262,13.331650735923587",
        "to.latitude": 52.51381461746885, "to.longitude": 13.335587343442882,
        "to.address": "52.51381461746885,13.335587343442882",
        "results": 1
    },
    {
        "from.latitude": 52.506898519891145, "from.longitude": 13.33243367181816,
        "from.address": "52.506898519891145,13.33243367181816",
        "to.latitude": 52.51651497417413, "to.longitude": 13.323818756533427,
        "to.address": "52.51651497417413,13.323818756533427",
        "results": 1
    },
    {
        "from.latitude": 52.50707205897473, "from.longitude": 13.331438922130621,
        "from.address": "52.50707205897473,13.331438922130621",
        "to.latitude": 52.51125656907616, "to.longitude": 13.305558238494228,
        "to.address": "52.51125656907616,13.305558238494228",
        "results": 1
    }
]

# ===== API Testing Functions =====
async def test_stations_api(base_url: str) -> dict:
    """Test stations endpoint"""
    results = {"stations": 0, "working": False}
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            for test in STATION_TESTS:
                try:
                    response = await client.get(f"{base_url}/locations/nearby", params=test)
                    if response.status_code == 200:
                        data = response.json()
                        if (isinstance(data, list) and 
                            len(data) > 0 and 
                            any(stop.get("type") == "stop" for stop in data)):
                            results["stations"] += 1
                except:
                    pass
            
            results["working"] = results["stations"] >= 2
            
    except Exception as e:
        print(f"Error testing stations at {base_url}: {str(e)}")
    
    return results

async def test_journeys_api(base_url: str) -> dict:
    """Test journeys endpoint"""
    results = {"routes": 0, "working": False}
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            for test in ROUTE_TESTS:
                try:
                    response = await client.get(f"{base_url}/journeys", params=test)
                    if response.status_code == 200:
                        data = response.json()
                        # Check valid journeys OR valid info response
                        valid_journeys = ("journeys" in data and 
                                        len(data["journeys"]) > 0 and 
                                        "legs" in data["journeys"][0] and
                                        len(data["journeys"][0]["legs"]) > 0)
                        
                        valid_info = ("info" in data and 
                                    data["info"].get("type") in ["no_stations", "no_results"])
                        
                        if valid_journeys or valid_info:
                            results["routes"] += 1
                except:
                    pass
            
            results["working"] = results["routes"] >= 2
            
    except Exception as e:
        print(f"Error testing journeys at {base_url}: {str(e)}")
    
    return results

# ===== Main Check Function =====
async def check_and_update_apis():
    """Check APIs and update state with hysteresis"""
    print(f"Running Health Check: {datetime.now()}")
    
    # Test STATIONS
    bvg_stations = await test_stations_api("https://v6.bvg.transport.rest")
    print(f"BVG Stations test: {bvg_stations['stations']}/3")
    
    if bvg_stations["working"]:
        await _api_manager.reset_failures("bvg_stations")
        await _api_manager.update_state(
            stations_base="https://v6.bvg.transport.rest",
            stations_name="bvg"
        )
        print("BVG is set for stations")
    else:
        should_switch = await _api_manager.handle_failure("bvg_stations")
        
        if should_switch:
            print("BVG stations failed, trying VBB...")
            vbb_stations = await test_stations_api("https://v6.vbb.transport.rest")
            print(f"VBB Stations test: {vbb_stations['stations']}/3")
            
            if vbb_stations["working"]:
                await _api_manager.update_state(
                    stations_base="https://v6.vbb.transport.rest",
                    stations_name="vbb"
                )
                await _api_manager.reset_failures("vbb_stations")
                print("VBB is set for stations")
            else:
                print("Both APIs failed for stations, keeping current")
    
    # Test JOURNEYS
    bvg_journeys = await test_journeys_api("https://v6.bvg.transport.rest")
    print(f"BVG Journeys test: {bvg_journeys['routes']}/3")
    
    if bvg_journeys["working"]:
        await _api_manager.reset_failures("bvg_journeys")
        await _api_manager.update_state(
            journeys_base="https://v6.bvg.transport.rest",
            journeys_name="bvg"
        )
        print("BVG is set for journeys")
    else:
        should_switch = await _api_manager.handle_failure("bvg_journeys")
        
        if should_switch:
            print("BVG journeys failed, trying VBB...")
            vbb_journeys = await test_journeys_api("https://v6.vbb.transport.rest")
            print(f"VBB Journeys test: {vbb_journeys['routes']}/3")
            
            if vbb_journeys["working"]:
                await _api_manager.update_state(
                    journeys_base="https://v6.vbb.transport.rest",
                    journeys_name="vbb"
                )
                await _api_manager.reset_failures("vbb_journeys")
                print("VBB is set for journeys")
            else:
                print("Both APIs failed for journeys, keeping current")
                
async def get_api_status() -> dict:
    """Get current API status for health check"""
    state = await _api_manager.get_state()
    return {
        "stations_api": {
            "provider": state.stations_name,
            "base_url": state.stations_base
        },
        "journeys_api": {
            "provider": state.journeys_name,
            "base_url": state.journeys_base
        },
        "last_check": state.last_check.isoformat()
    }

# ===== Public API =====
async def get_current_stations_api_base() -> str:
    """Get current stations API base URL"""
    state = await _api_manager.get_state()
    return state.stations_base

async def get_current_journeys_api_base() -> str:
    """Get current journeys API base URL"""
    state = await _api_manager.get_state()
    return state.journeys_base

# Backward compatibility
def get_current_api_base():
    """Deprecated - use async version"""
    return "https://v6.bvg.transport.rest"