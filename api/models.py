from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class RoutePoint(BaseModel):
    """Route point (stop or coordinates)"""
    name: str
    latitude: float
    longitude: float
    is_stop: bool  # Whether this is a stop or just coordinates

class RouteLeg(BaseModel):
    """Segment of a route"""
    start: RoutePoint
    end: RoutePoint
    type: str  # "walking", "subway", "suburban", "bus"
    line: Optional[str] = None  # "U12", "S7", None for walking segments
    direction: Optional[str] = None  # Direction of travel
    departure_time: datetime
    arrival_time: datetime
    delay_minutes: Optional[int] = None  # Delay in minutes
    distance: Optional[int] = None  # Distance in meters for walking segments
    warnings: List[str] = Field(default_factory=list)  # Brief warnings

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
