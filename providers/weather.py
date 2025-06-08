import os
import json
from typing import Optional
from providers.base import BaseProvider
from api.models import Weather

class WeatherProvider(BaseProvider):
    """Provider for OpenWeatherMap weather + air quality data"""
    
    # TU Berlin campus coordinates as default
    DEFAULT_LAT = 52.51254994596774
    DEFAULT_LON = 13.326949151892109
    
    def __init__(self):
        super().__init__()
        self.base_url = "https://api.openweathermap.org/data/2.5"
        self.api_key = os.getenv("OPENWEATHER_API_KEY")
        
        if not self.api_key:
            print("Warning: OPENWEATHER_API_KEY not set!")
    
    async def get_weather(
        self, 
        lat: Optional[float] = None, 
        lon: Optional[float] = None
    ) -> Optional[Weather]:
        """
        Get weather data (temp, description, icon, air quality)
        
        Args:
            lat: Latitude (defaults to TU Berlin campus)
            lon: Longitude (defaults to TU Berlin campus)
            
        Returns:
            Weather data or None if error
        """
        # Use default coordinates if not provided
        if lat is None:
            lat = self.DEFAULT_LAT
        if lon is None:
            lon = self.DEFAULT_LON
        
        if not self.api_key:
            print("No API key available")
            return None
            
        try:
            # Prepare URLs
            weather_url = f"{self.base_url}/weather"
            air_url = f"{self.base_url}/air_pollution"
            
            params = {
                "lat": lat,
                "lon": lon,
                "appid": self.api_key,
                "units": "metric"
            }
            
            # Make both requests
            weather_response = await self.client.get(weather_url, params=params)
            weather_response.raise_for_status()
            weather_data = weather_response.json()
            
            air_response = await self.client.get(air_url, params=params)
            air_response.raise_for_status()
            air_data = air_response.json()
            
            # Create Weather object
            weather = Weather(
                temperature=weather_data['main']['temp'],
                description=weather_data['weather'][0]['description'],
                icon_url=f"https://openweathermap.org/img/w/{weather_data['weather'][0]['icon']}.png",
                air_quality_index=air_data['list'][0]['main']['aqi']
            )
            
            return weather
            
        except Exception as e:
            print(f"Error fetching weather data: {str(e)}")
            return None