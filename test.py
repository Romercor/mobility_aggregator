import asyncio
import httpx
import time
import random
import json
from datetime import datetime, timedelta

# Base URL for your API
BASE_URL = "http://localhost:8000/api"

# Test locations around TU Berlin campus
TEST_LOCATIONS = [
    (52.512, 13.326),  # Main Building
    (52.516, 13.323),  # Mathematics Building
    (52.509, 13.332),  # Near Zoo
    (52.508, 13.315),  # Southwest corner
    (52.520, 13.335),  # Northeast corner
    (52.514, 13.327),  # Library
]

# Generate random route pairs
ROUTE_PAIRS = []
for _ in range(10):
    start = random.choice(TEST_LOCATIONS)
    # Make sure end is different from start
    end = random.choice([loc for loc in TEST_LOCATIONS if loc != start])
    ROUTE_PAIRS.append((start, end))

# Test parameters
TRANSPORT_TYPES = [None, "bus", "subway"]
RESULT_COUNTS = [1, 3, 5]

async def test_nearest_stations(client, location, transport_type=None, results=3):
    """Test the nearest-stations endpoint"""
    lat, lon = location
    
    # Add tiny random variation to coordinates to test cache behavior
    lat += random.uniform(-0.0001, 0.0001)
    lon += random.uniform(-0.0001, 0.0001)
    
    params = {
        "lat": lat,
        "lon": lon,
        "results": results
    }
    
    if transport_type:
        params["transport_type"] = transport_type
    
    start_time = time.time()
    try:
        response = await client.get(f"{BASE_URL}/nearest-stations", params=params)
        duration = time.time() - start_time
        
        result = {
            "endpoint": "nearest-stations",
            "status_code": response.status_code,
            "duration_ms": int(duration * 1000),
            "success": response.status_code == 200,
        }
        
        if response.status_code == 200:
            data = response.json()
            result["stops_count"] = len(data.get("stops", []))
        
        return result
    except Exception as e:
        duration = time.time() - start_time
        return {
            "endpoint": "nearest-stations",
            "status_code": 0,
            "duration_ms": int(duration * 1000),
            "success": False,
            "error": str(e)
        }

async def test_nearby_bikes(client, location, radius=500, limit=5):
    """Test the bikes/nearby endpoint"""
    lat, lon = location
    
    # Add small variation
    lat += random.uniform(-0.0001, 0.0001)
    lon += random.uniform(-0.0001, 0.0001)
    
    params = {
        "lat": lat,
        "lon": lon,
        "radius": radius,
        "limit": limit
    }
    
    start_time = time.time()
    try:
        response = await client.get(f"{BASE_URL}/bikes/nearby", params=params)
        duration = time.time() - start_time
        
        result = {
            "endpoint": "bikes/nearby",
            "status_code": response.status_code,
            "duration_ms": int(duration * 1000),
            "success": response.status_code == 200,
        }
        
        if response.status_code == 200:
            data = response.json()
            result["bikes_count"] = len(data.get("bikes", []))
        
        return result
    except Exception as e:
        duration = time.time() - start_time
        return {
            "endpoint": "bikes/nearby",
            "status_code": 0,
            "duration_ms": int(duration * 1000),
            "success": False,
            "error": str(e)
        }

async def test_routes(client, start_loc, end_loc, results=2, stopovers=True):
    """Test the pretty-routes endpoint"""
    start_lat, start_lon = start_loc
    end_lat, end_lon = end_loc
    
    # Generate a departure time within the next 2 hours
    minutes_from_now = random.randint(15, 120)
    departure_time = (datetime.now() + timedelta(minutes=minutes_from_now)).strftime("%Y-%m-%dT%H:%M:%S+02:00")
    
    params = {
        "from_lat": start_lat,
        "from_lon": start_lon,
        "to_lat": end_lat,
        "to_lon": end_lon,
        "results": results,
        "stopovers": str(stopovers).lower(),
        "departure": departure_time
    }
    
    start_time = time.time()
    try:
        response = await client.get(f"{BASE_URL}/pretty-routes", params=params)
        duration = time.time() - start_time
        
        result = {
            "endpoint": "pretty-routes",
            "status_code": response.status_code,
            "duration_ms": int(duration * 1000),
            "success": response.status_code == 200,
        }
        
        if response.status_code == 200:
            data = response.json()
            result["routes_count"] = len(data.get("routes", []))
        
        return result
    except Exception as e:
        duration = time.time() - start_time
        return {
            "endpoint": "pretty-routes",
            "status_code": 0,
            "duration_ms": int(duration * 1000),
            "success": False,
            "error": str(e)
        }

async def run_mixed_batch(batch_size=10):
    """Run a mixed batch of requests testing different endpoints"""
    async with httpx.AsyncClient(timeout=30) as client:
        tasks = []
        
        for _ in range(batch_size):
            # Randomly choose which endpoint to test
            endpoint_type = random.choices(
                ["stations", "bikes", "routes"], 
                weights=[0.3, 0.3, 0.4],  # Routes are slightly more important
                k=1
            )[0]
            
            if endpoint_type == "stations":
                location = random.choice(TEST_LOCATIONS)
                transport_type = random.choice(TRANSPORT_TYPES)
                results = random.choice(RESULT_COUNTS)
                task = test_nearest_stations(client, location, transport_type, results)
                
            elif endpoint_type == "bikes":
                location = random.choice(TEST_LOCATIONS)
                radius = random.choice([300, 500, 1000])
                limit = random.choice([3, 5, 10])
                task = test_nearby_bikes(client, location, radius, limit)
                
            else:  # routes
                route_pair = random.choice(ROUTE_PAIRS)
                results = random.choice([1, 2, 3])
                stopovers = random.choice([True, False])
                task = test_routes(client, route_pair[0], route_pair[1], results, stopovers)
            
            tasks.append(task)
        
        # Run all tasks concurrently
        return await asyncio.gather(*tasks)

async def main():
    """Main stress test function"""
    total_requests = 100
    batch_size = 10
    
    print(f"Starting comprehensive stress test with {total_requests} total requests, {batch_size} concurrent...")
    print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
    
    results_by_endpoint = {
        "nearest-stations": [],
        "bikes/nearby": [],
        "pretty-routes": []
    }
    
    # Run batches until we've sent all requests
    start_time = time.time()
    for i in range(0, total_requests, batch_size):
        current_batch = min(batch_size, total_requests - i)
        print(f"Running batch {i//batch_size + 1} with {current_batch} requests...")
        
        batch_results = await run_mixed_batch(current_batch)
        
        # Categorize results by endpoint
        for result in batch_results:
            endpoint = result["endpoint"]
            results_by_endpoint[endpoint].append(result)
    
    # Calculate and print overall statistics
    elapsed = time.time() - start_time
    total_success = sum(1 for endpoint_results in results_by_endpoint.values() 
                       for result in endpoint_results if result["success"])
    
    print("\n=== OVERALL STRESS TEST RESULTS ===")
    print(f"Total requests: {total_requests}")
    print(f"Total elapsed time: {elapsed:.2f} seconds")
    print(f"Requests per second: {total_requests / elapsed:.2f}")
    print(f"Overall success rate: {(total_success / total_requests * 100):.2f}%")
    
    # Print statistics for each endpoint
    for endpoint, results in results_by_endpoint.items():
        if not results:
            continue
            
        response_times = [r["duration_ms"] for r in results]
        success_count = sum(1 for r in results if r["success"])
        
        print(f"\n--- {endpoint} ({len(results)} requests) ---")
        print(f"Success rate: {(success_count / len(results) * 100):.2f}%")
        
        if response_times:
            response_times.sort()
            avg_response = sum(response_times) / len(response_times)
            median_response = response_times[len(response_times) // 2]
            p95_response = response_times[int(len(response_times) * 0.95)]
            max_response = max(response_times)
            
            print(f"Average response time: {avg_response:.2f} ms")
            print(f"Median response time: {median_response} ms")
            print(f"95th percentile response time: {p95_response} ms")
            print(f"Maximum response time: {max_response} ms")
        
        # Print failures for this endpoint
        failures = [r for r in results if not r["success"]]
        if failures:
            print(f"Failures: {len(failures)}")
            for f in failures[:3]:  # Show first 3 failures
                print(f"  - Status: {f['status_code']}, Time: {f['duration_ms']} ms, Error: {f.get('error', 'Unknown')}")
            
            if len(failures) > 3:
                print(f"  ... and {len(failures) - 3} more failures")

if __name__ == "__main__":
    asyncio.run(main())