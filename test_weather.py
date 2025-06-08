# -*- coding: utf-8 -*-
"""
Standalone weather function
Gets temperature, description, icon URL, and air quality index
"""

import requests
import os
import json
from dotenv import load_dotenv

load_dotenv()

def get_weather(lat=52.51254994596774, lon=13.326949151892109):
    """
    Get weather data
    
    Args:
        lat: Latitude (default: TU Berlin)
        lon: Longitude (default: TU Berlin)
    
    Returns:
        JSON string with temperature, description, icon_url, air_quality_index
        or None if error
    """
    api_key = os.getenv("OPENWEATHER_API_KEY")
    
    if not api_key:
        print("ERROR: OPENWEATHER_API_KEY not found in environment!")
        return None
    
    try:
        # Weather API
        weather_url = f"https://api.openweathermap.org/data/2.5/weather"
        weather_params = {
            "lat": lat,
            "lon": lon,
            "appid": api_key,
            "units": "metric"
        }
        
        # Air Quality API
        air_url = f"https://api.openweathermap.org/data/2.5/air_pollution"
        air_params = {
            "lat": lat,
            "lon": lon,
            "appid": api_key
        }
        
        # Make requests
        weather_response = requests.get(weather_url, params=weather_params, timeout=10)
        weather_response.raise_for_status()
        weather_data = weather_response.json()
        
        air_response = requests.get(air_url, params=air_params, timeout=10)
        air_response.raise_for_status()
        air_data = air_response.json()
        
        # Extract what we need
        result = {
            "temperature": weather_data['main']['temp'],
            "description": weather_data['weather'][0]['description'],
            "icon_url": f"https://openweathermap.org/img/w/{weather_data['weather'][0]['icon']}.png",
            "air_quality_index": air_data['list'][0]['main']['aqi']
        }
        
        return json.dumps(result, ensure_ascii=False)
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            print("ERROR: Invalid API key!")
        elif e.response.status_code == 429:
            print("ERROR: Rate limit exceeded!")
        else:
            print(f"HTTP ERROR: {e.response.status_code}")
        return None
        
    except requests.exceptions.RequestException as e:
        print(f"NETWORK ERROR: {e}")
        return None
        
    except KeyError as e:
        print(f"DATA ERROR: Missing field {e}")
        return None
        
    except Exception as e:
        print(f"UNEXPECTED ERROR: {e}")
        return None

# Test the function
if __name__ == "__main__":
    print("Testing weather function...")
    
    # Test with default coordinates (TU Berlin)
    result_json = get_weather()
    
    if result_json:
        print("SUCCESS!")
        print(result_json)
        
        # Parse for individual values
        result = json.loads(result_json)
        print(f"Temperature: {result['temperature']}°C")
        print(f"Description: {result['description']}")
        print(f"Icon URL: {result['icon_url']}")
        print(f"Air Quality: {result['air_quality_index']} (1=Good, 5=Very Poor)")
    else:
        print("FAILED!")
        
    # Test with custom coordinates
    print("\nTesting with custom coordinates...")
    custom_result_json = get_weather(lat=52.520, lon=13.405)  # Berlin center
    
    if custom_result_json:
        print("SUCCESS!")
        print(custom_result_json)
        
        # Parse for individual values
        custom_result = json.loads(custom_result_json)
        print(f"Temperature: {custom_result['temperature']}°C")
        print(f"Description: {custom_result['description']}")
        print(f"Air Quality: {custom_result['air_quality_index']}")
    else:
        print("FAILED!")