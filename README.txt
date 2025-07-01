================================================================================
                        TU BERLIN CAMPUS ROUTER API
                              Version 1.5
================================================================================

INSTALLATION
------------
1. Install Docker Desktop: https://docker.com
2. Get free OpenWeatherMap API key: https://openweathermap.org/api
3. Load image: docker load < tu-router.tar  
4. Start with API key: docker run -d -p 8000:8000 -e OPENWEATHER_API_KEY="your_key_here" --name campus tu-router
5. Access API: http://localhost:8000/docs

Alternative: Use .env file
echo "OPENWEATHER_API_KEY=your_key_here" > .env
docker run -d -p 8000:8000 --env-file .env --name campus tu-router

Stop service: docker stop campus
View logs: docker logs campus

================================================================================
API ENDPOINTS - COPY & PASTE EXAMPLES
================================================================================
STUDENT SCHEDULE(MOSES TU BERLIN)
----------------
Response: List of student lectures with course name, instructor, location, and time schedule

# Basic query with stupo and semester
http://localhost:8000/api/student-schedule?stupo=24544&semester=2

# Include past lectures (filter_dates=false)
http://localhost:8000/api/student-schedule?stupo=24544&semester=2&filter_dates=false

# All parameters
http://localhost:8000/api/student-schedule?stupo=24544&semester=2&filter_dates=true

WEATHER DATA
------------
Response: Current weather with temperature, description, icon URL, and air quality index

# TU Berlin campus (default location - TU Berlin campus)
http://localhost:8000/api/weather

# Custom location with combined coordinates
http://localhost:8000/api/weather?coords=52.520,13.405

# Custom location with separate parameters
http://localhost:8000/api/weather?lat=52.520&lon=13.405

ROUTE PLANNING
--------------
Response formats:
- /routes: Detailed JSON with legs, transfers, platforms, delays
- /pretty-routes: Simplified JSON with human-readable steps  
- /raw-routes: Unprocessed BVG API response
- Empty routes: {"routes":[]} for distances <200m

# Basic route with coordinates as separate parameters
http://localhost:8000/api/routes?from_lat=52.5133&from_lon=13.3247&to_lat=52.5147&to_lon=13.3149

# Using combined coordinate format
http://localhost:8000/api/routes?from=52.5133,13.3247&to=52.5147,13.3149

# Pretty format (human-readable steps)
http://localhost:8000/api/pretty-routes?from=52.5133,13.3247&to=52.5147,13.3149

# Multiple route alternatives (1-5)
http://localhost:8000/api/routes?from=52.5138,13.3266&to=52.5130,13.3217&results=3

# Include intermediate stops
http://localhost:8000/api/routes?from=52.5125,13.3270&to=52.5070,13.3321&stopovers=true

# Specific departure time (ISO 8601)
http://localhost:8000/api/routes?from=52.5141,13.3295&to=52.5053,13.3039&departure=2025-05-28T15:30:00%2B02:00

# With public transport route geometry (polylines) for map visualization
http://localhost:8000/api/routes?from=52.5133,13.3247&to=52.5147,13.3149&polylines=true

# All parameters combined
http://localhost:8000/api/routes?from=52.5141,13.3295&to=52.5053,13.3039&results=5&stopovers=true&departure=2025-05-28T09:00:00%2B02:00&polylines=true

# Raw BVG API response (requires separate lat/lon)
http://localhost:8000/api/raw-routes?from_lat=52.5133&from_lon=13.3247&to_lat=52.5147&to_lon=13.3149&results=2&stopovers=false

BIKE SHARING (NEXTBIKE)
-----------------------
Response: List of bikes with provider, location, distance, vehicle_id

# Basic query with separate lat/lon
http://localhost:8000/api/bikes/nearby?lat=52.5125&lon=13.3270

# Using combined coordinate format
http://localhost:8000/api/bikes/nearby?coords=52.5130,13.3217

# Custom radius in meters (10-2000)
http://localhost:8000/api/bikes/nearby?lat=52.5125&lon=13.3270&radius=1000

# Custom limit (1-20)
http://localhost:8000/api/bikes/nearby?lat=52.5125&lon=13.3270&limit=20

# All parameters
http://localhost:8000/api/bikes/nearby?coords=52.5141,13.3295&radius=1500&limit=15

PUBLIC TRANSPORT STATIONS
-------------------------
Response: List of stations with name, distance, available transport types

# Basic query with combined coordinates
http://localhost:8000/api/nearest-stations?coords=52.5125,13.3270

# Using separate lat/lon parameters
http://localhost:8000/api/nearest-stations?lat=52.5125&lon=13.3270

# Custom number of results (1-10)
http://localhost:8000/api/nearest-stations?coords=52.5125,13.3270&results=10

# Filter by single transport type
http://localhost:8000/api/nearest-stations?coords=52.5125,13.3270&transport_type=subway
http://localhost:8000/api/nearest-stations?coords=52.5125,13.3270&transport_type=bus
http://localhost:8000/api/nearest-stations?coords=52.5125,13.3270&transport_type=tram
http://localhost:8000/api/nearest-stations?coords=52.5125,13.3270&transport_type=suburban

# All parameters combined
http://localhost:8000/api/nearest-stations?lat=52.5125&lon=13.3270&results=5&transport_type=bus

MENSA MENUS
-----------
Response: Weekly menu with dishes grouped by category, prices, vegan/vegetarian flags

# Get menu by mensa name (hardenbergstrasse|marchstrasse|veggie)
http://localhost:8000/api/mensa/hardenbergstrasse/menu
http://localhost:8000/api/mensa/marchstrasse/menu
http://localhost:8000/api/mensa/veggie/menu

# Force refresh (bypass cache)
http://localhost:8000/api/mensa/hardenbergstrasse/menu?force_refresh=true

# Get all menus in single request
http://localhost:8000/api/mensa/all-menus

# Get all menus with forced refresh
http://localhost:8000/api/mensa/all-menus?force_refresh=true

# List available mensa names
http://localhost:8000/api/mensa/list

# Refresh all menus (POST request - use curl or Postman)
curl -X POST http://localhost:8000/api/mensa/refresh

SYSTEM MONITORING
-----------------
# Health check (GET)
http://localhost:8000/api/health

# Cache statistics (GET)
http://localhost:8000/api/cache/stats

# Clean expired cache entries (POST)
curl -X POST http://localhost:8000/api/cache/cleanup
# PowerShell: Invoke-WebRequest -Method POST http://localhost:8000/api/cache/cleanup

# Clear entire cache (DELETE)
curl -X DELETE http://localhost:8000/api/cache/clear
# PowerShell: Invoke-WebRequest -Method DELETE http://localhost:8000/api/cache/clear

Note: 
The service automatically runs health checks every 10 minutes for all core services. 
Automatic switch between BVG and VBB provider on failure. 
see the results in http://localhost:8000/api/health

DATABASE (OPTIONAL)
------------------
The API can use PostgreSQL for persistent storage of mensa menus and student schedules.
Without database: Data cached in memory only, cleared on restart
With database: Persistent cache, faster subsequent requests

Required environment variables:
DB_HOST=localhost
DB_PORT=5432  
DB_NAME=campus_router
DB_USER=campus_user
DB_PASSWORD=campus_pass

Docker with database:
docker run -d -p 8000:8000 \
  -e OPENWEATHER_API_KEY="your_key_here" \
  -e DB_HOST="your_postgres_host" \
  -e DB_PASSWORD="your_db_password" \
  --name campus tu-router

Database stores: Mensa menus (1 week cache), Student schedules (2 week cache)
Health check: http://localhost:8000/api/database/health
================================================================================
API PARAMETERS REFERENCE
================================================================================
WEATHER:
- coords: "lat,lon" OR use lat + lon separately
- Default location: TU Berlin campus (52.512, 13.327)
- Response includes: temperature (°C), description, icon URL, air quality index (1-5)

ROUTES:
- from: "lat,lon" OR use from_lat + from_lon separately
- to: "lat,lon" OR use to_lat + to_lon separately  
- results: 1-5 (number of route alternatives)
- stopovers: true|false (include intermediate stops)
- departure: ISO 8601 datetime with timezone

BIKES:
- coords: "lat,lon" OR use lat + lon separately
- radius: 10-2000 meters (search area)
- limit: 1-20 (max bikes to return)

STATIONS:
- coords: "lat,lon" OR use lat + lon separately
- results: 1-10 (number of stations)
- transport_type: subway|bus|tram|suburban

MENSA:
- force_refresh: true|false (bypass cache)

================================================================================
TECHNICAL NOTES
================================================================================
- Weather API requires OpenWeatherMap API key (free: https://openweathermap.org/api)
- Air Quality Index: 1=Good, 2=Fair, 3=Moderate, 4=Poor, 5=Very Poor
- Weather icons: Direct URLs to OpenWeatherMap icon images
- Maximum route duration: 30 minutes
- Coordinate format: Decimal degrees (WGS84)
- Time format: ISO 8601 with timezone
- Cache TTL: Routes 5min, Bikes 30s, Mensa 1 week
- First mensa request: ~20s (browser startup)
- API documentation: http://localhost:8000/docs
- OpenAPI schema: http://localhost:8000/openapi.json
- Scope: Campus area routes (Scenario A)

================================================================================
