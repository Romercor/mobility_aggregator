import asyncio
import httpx
import json
from datetime import datetime

async def test_bvg_api():
    base_url = "https://v6.bvg.transport.rest"
    
    async with httpx.AsyncClient() as client:
        # Тест 1: Поиск остановок поблизости через /locations/nearby
        print("\n1. Testing nearby stops...")
        response = await client.get(
            f"{base_url}/locations/nearby", 
            params={
                "latitude": 52.52,
                "longitude": 13.405,
                "distance": 500,
                "results": 10,
                "stops": "true",  # Только остановки
                "addresses": "false",
                "poi": "false"
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            stops = [item for item in data if item.get('type') == 'stop']
            print(f"✅ Success! Found {len(stops)} stops nearby.")
            
            if len(stops) > 0:
                first_stop = stops[0]
                stop_id = first_stop.get('id')
                stop_name = first_stop.get('name')
                print(f"First stop: {stop_name} (ID: {stop_id})")
                
                # Тест 2: Получение отправлений для остановки
                if stop_id:
                    print(f"\n2. Testing departures for {stop_name}...")
                    departures_response = await client.get(
                        f"{base_url}/stops/{stop_id}/departures",
                        params={
                            "duration": 30,
                            "results": 5
                        }
                    )
                    
                    if departures_response.status_code == 200:
                        departures_data = departures_response.json()
                        departures = departures_data.get('departures', [])
                        print(f"✅ Success! Found {len(departures)} departures.")
                        
                        # Показать первые 2 отправления
                        for i, departure in enumerate(departures[:2]):
                            line = departure.get('line', {}).get('name', 'Unknown')
                            direction = departure.get('direction', 'Unknown')
                            when = departure.get('when')
                            if when:
                                when_dt = datetime.fromisoformat(when.replace('Z', '+00:00'))
                                when_str = when_dt.strftime('%H:%M:%S')
                            else:
                                when_str = "Unknown"
                            
                            print(f"   {i+1}. Line {line} to {direction}, departing at {when_str}")
                    else:
                        print(f"❌ Error getting departures: {departures_response.status_code}")
                        print(departures_response.text)
        else:
            print(f"❌ Error getting nearby stops: {response.status_code}")
            print(response.text)

if __name__ == "__main__":
    asyncio.run(test_bvg_api())