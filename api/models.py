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
    platform: Optional[str] = None  # Platform information if available
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

class RouteStep(BaseModel):
    """User-friendly step in a journey"""
    type: str  # "walking", "subway", "bus", etc.
    instruction: str  # "Walk to U Ernst-Reuter-Platz", "Take U12 towards Warschauer Straße"
    duration: str  # "5 min"
    distance: Optional[str] = None  # "365m" (for walking)
    platform: Optional[str] = None  # "Platform 2" (for transit)
    icon: str  # "walking", "subway", "bus", etc.

class PrettyRoute(BaseModel):
    """User-friendly route representation"""
    summary: str  # "Walk 5 min → U12 (2 min) → Walk 1 min"
    steps: List[RouteStep]
    alerts: List[str]  # Important warnings/notifications
    departure: str  # "09:01"
    arrival: str  # "09:09"
    total_duration: str  # "8 minutes"
    transfers: int
    walking_distance: str  # "412m"
    walking_time: str  # "6 min"
    
class PrettyRouteResponse(BaseModel):
    """API response with pretty routes"""
    routes: List[PrettyRoute]