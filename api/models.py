from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class RoutePoint(BaseModel):
    """Route point (stop or coordinates)"""
    name: str
    latitude: float
    longitude: float
    is_stop: bool

class Stopover(BaseModel):
    """Intermediate stop in a route leg"""
    name: str
    latitude: float
    longitude: float
    arrival_time: Optional[datetime] = None
    departure_time: Optional[datetime] = None
    platform: Optional[str] = None
class RouteLeg(BaseModel):
    """Segment of a route"""
    start: RoutePoint
    end: RoutePoint
    type: str
    line: Optional[str] = None
    direction: Optional[str] = None
    departure_time: datetime
    arrival_time: datetime
    delay_minutes: Optional[int] = None
    distance: Optional[int] = None
    platform: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    stopovers: List[Stopover] = Field(default_factory=list)
class Route(BaseModel):
    """Complete route"""
    legs: List[RouteLeg]
    duration_minutes: int
    transfers: int
    walking_distance: int
    departure_time: datetime
    arrival_time: datetime

class RouteResponse(BaseModel):
    """API response with routes"""
    routes: List[Route]

class RouteStep(BaseModel):
    """User-friendly step in a journey"""
    type: str
    instruction: str
    duration: str
    distance: Optional[str] = None
    platform: Optional[str] = None
    icon: str

class PrettyRoute(BaseModel):
    """User-friendly route representation"""
    summary: str
    steps: List[RouteStep]
    alerts: List[str]
    departure: str
    arrival: str
    total_duration: str
    transfers: int
    walking_distance: str
    walking_time: str 
    
class PrettyRouteResponse(BaseModel):
    """API response with pretty routes"""
    routes: List[PrettyRoute]

class BikeItem(BaseModel):
    """Bike sharing item"""
    provider: str
    lat: float
    lon: float
    vehicle_id: str
    distance: float

class BikeResponse(BaseModel):
    """API response with bikes"""
    bikes: List[BikeItem]