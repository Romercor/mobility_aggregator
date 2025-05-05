from typing import List, Optional, Literal, Dict, Any, Union
from pydantic import BaseModel, Field, field_validator
from datetime import datetime

class StopInfo(BaseModel): 
    """Information about a public transport stop"""
    stop_id: str
    name: str
    distance: float # Distance to user's location in meters

class DepartureInfo(BaseModel):
    """Information about a departure from a stop"""
    line: str
    direction: str
    departure_time: datetime
    platform: Optional[str] = None
class VehicleItem(BaseModel):
    """Base class for all mobility items"""
    provider: Literal["voi", "tier", "bvg"]
    type: Literal["scooter", "bus", "train", "stop"]
    lat: float
    lon: float
class ScooterItem(VehicleItem):
    """Information about a scooter"""
    type: Literal["scooter"] = "scooter" 
    battery_level: float
    vehicle_id:str
    @field_validator('battery_level')
    def validate_battery(cls, v):
        if v < 0 or v > 100:
            raise ValueError('Battery level must be between 0 and 100')
        return v
class StopItem(VehicleItem):
    """Information about a public transport stop with departures"""
    type: Literal["stop"] = "stop"
    stop_info: StopInfo
    departures: List[DepartureInfo] = []

TransportItem = Union[ScooterItem, StopItem]

class AggregatedResponse(BaseModel):
    """Response model with all transport items"""
    items: List[TransportItem]
