from typing import List
import random
import math

from providers.base import BaseProvider
from api.models import TransportItem, ScooterItem

class VoiProvider(BaseProvider):
    """Provider for VOI scooters data (mock implementation)"""
    
    def __init__(self):
        super().__init__()
        self.provider_name = "voi"
    
    async def get_vehicles(self, lat: float, lon: float, radius: float) -> List[TransportItem]:
        """Get VOI scooters within radius (mock data)"""
        scooters = []
        
        # Generate 5 random scooters
        for i in range(5):
            # Random offset within approximately radius meters
            lat_offset = (random.random() - 0.5) * radius / 111000
            lon_offset = (random.random() - 0.5) * radius / (111000 * math.cos(math.radians(lat)))
            
            scooter = ScooterItem(
                provider=self.provider_name,
                lat=lat + lat_offset,
                lon=lon + lon_offset,
                battery_level=random.uniform(20, 100),
                vehicle_id=f"{self.provider_name}-{i+1000}"
            )
            scooters.append(scooter)
        
        return scooters