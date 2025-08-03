# 🚀 TU Berlin Campus Router API

[![API Status](https://img.shields.io/badge/API-Active-green)](http://localhost:8000/docs)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://hub.docker.com/)
[![OpenAPI](https://img.shields.io/badge/OpenAPI-3.0-orange)](http://localhost:8000/docs)

A comprehensive mobility aggregation API for TU Berlin campus, providing route planning, public transport information, bike sharing, weather data, mensa menus, and student schedules.

## 🎯 Quick Start

```bash
# 1. Get your free OpenWeatherMap API key
# Visit: https://openweathermap.org/api

# 2. Clone and build the container
git clone https://github.com/your-username/tu-berlin-campus-router.git
cd tu-berlin-campus-router
docker build -t tu-router .

# 3. Start the API
docker run -d -p 8000:8000 -e OPENWEATHER_API_KEY="your_key_here" --name campus tu-router

# 4. Test the API
curl "http://localhost:8000/api/routes?from=52.5133,13.3247&to=52.5147,13.3149"

# 5. Explore interactive docs
open http://localhost:8000/docs
```

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Campus Router   │    │  External APIs  │
│                 │◄──►│      API         │◄──►│                 │
│ (Your App)      │    │                  │    │ BVG/VBB        │
└─────────────────┘    │  ┌─────────────┐ │    │ NextBike       │
                       │  │   Cache     │ │    │ OpenWeather    │
┌─────────────────┐    │  │   System    │ │    │ TU Moses       │
│   PostgreSQL    │◄──►│  └─────────────┘ │    │ Mensa STW      │
│   (Optional)    │    └──────────────────┘    └─────────────────┘
└─────────────────┘
```

### Core Components
- **Route Planning**: BVG/VBB public transport integration with intelligent fallback
- **Bike Sharing**: NextBike availability and location data
- **Weather Service**: OpenWeatherMap with air quality index
- **Mensa Integration**: Real-time menu scraping with weekly caching
- **Student Schedules**: Moses TU Berlin integration for course schedules
- **Multi-layer Caching**: Memory + optional PostgreSQL persistence
- **Health Monitoring**: Automatic API switching and status tracking

## 📚 API Reference

### 🚌 Route Planning
Get optimized public transport routes across (TU) Berlin.

```bash
# Basic route planning
GET /api/routes?from=52.5133,13.3247&to=52.5147,13.3149

# With multiple alternatives and stopovers
GET /api/routes?from=52.5133,13.3247&to=52.5147,13.3149&results=3&stopovers=true

# Scheduled departure
GET /api/routes?from=52.5133,13.3247&to=52.5147,13.3149&departure=2025-05-28T15:30:00%2B02:00
```

<details>
<summary>📋 Route Response Example</summary>

```json
{
  "routes": [
    {
      "legs": [
        {
          "start": {"name": "TU Berlin Main Building", "latitude": 52.5133, "longitude": 13.3247},
          "end": {"name": "Ernst-Reuter-Platz", "latitude": 52.5147, "longitude": 13.3149},
          "type": "subway",
          "line": "U2",
          "direction": "Pankow",
          "departure_time": "2025-05-28T15:32:00+02:00",
          "arrival_time": "2025-05-28T15:35:00+02:00",
          "platform": "Gleis 1"
        }
      ],
      "duration_minutes": 8,
      "transfers": 0,
      "walking_distance": 120
    }
  ]
}
```
</details>

### 🚲 Bike Sharing
Find available NextBike bikes near any location.

```bash
# Find nearby bikes
GET /api/bikes/nearby?coords=52.5125,13.3270&radius=1000&limit=10
```

### 🌤️ Weather & Air Quality
Current weather conditions with air quality index.

```bash
# Campus weather (default)
GET /api/weather

# Custom location
GET /api/weather?coords=52.520,13.405
```

### 🍽️ Mensa Menus
Weekly menus from TU Berlin cafeterias.

```bash
# Get specific mensa menu
GET /api/mensa/hardenbergstrasse/menu

# All mensas at once
GET /api/mensa/all-menus

# Available mensa list
GET /api/mensa/list
```

### 📚 Student Schedules
Access your course schedule from Moses TU Berlin.

```bash
# Get your lectures (requires stupo number)
GET /api/student-schedule?stupo=24544&semester=2
```

### 🚉 Station Finder
Locate nearest public transport stations.

```bash
# Find stations by transport type
GET /api/nearest-stations?coords=52.5125,13.3270&transport_type=subway
```

## 🛠️ Installation & Configuration

### Docker Installation (Recommended)
```bash
# Load the image
docker load < tu-router.tar

# Run with environment variables
docker run -d -p 8000:8000 \
  -e OPENWEATHER_API_KEY="your_key_here" \
  --name campus tu-router

# Alternative: Using .env file
echo "OPENWEATHER_API_KEY=your_key_here" > .env
docker run -d -p 8000:8000 --env-file .env --name campus tu-router
```

### Optional Database Setup
For persistent caching and better performance:

```bash
docker run -d -p 8000:8000 \
  -e OPENWEATHER_API_KEY="your_key_here" \
  -e DB_HOST="your_postgres_host" \
  -e DB_NAME="campus_router" \
  -e DB_USER="campus_user" \
  -e DB_PASSWORD="your_db_password" \
  --name campus tu-router
```

### Environment Variables
| Variable | Required | Description |
|----------|----------|-------------|
| `OPENWEATHER_API_KEY` | ✅ | Free API key from OpenWeatherMap |
| `DB_HOST` | ❌ | PostgreSQL host for persistent storage |
| `DB_PORT` | ❌ | Database port (default: 5432) |
| `DB_NAME` | ❌ | Database name (default: campus_router) |
| `DB_USER` | ❌ | Database user (default: campus_user) |
| `DB_PASSWORD` | ❌ | Database password |

## 🔧 Development

### Project Structure
```
├── api/                    # API models and endpoints
├── providers/             # External service integrations
│   ├── bvg.py            # BVG/VBB transport API
│   ├── nextbike.py       # Bike sharing
│   ├── weather.py        # Weather service
│   ├── mensa.py          # Cafeteria menus
│   └── moses.py          # Student schedules
├── database/             # Database models and services
├── utils/                # Utilities (caching, geocoding)
└── main.py              # FastAPI application
```

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export OPENWEATHER_API_KEY="your_key_here"

# Run development server
python main.py
```

## 📊 Monitoring & Health

### Health Check
```bash
# System health overview
GET /api/health

# Database health (if configured)
GET /api/database/health

# Cache statistics
GET /api/cache/stats
```

### Cache Management
```bash
# View cache statistics
GET /api/cache/stats

# Clean expired entries
POST /api/cache/cleanup

# Clear all caches (use carefully)
DELETE /api/cache/clear
```

## 🚨 Troubleshooting

### Common Issues

**API Returns Empty Routes**
- Routes under 200m walking distance return `{"routes":[]}`
- Check coordinates are within Berlin/Brandenburg area
- Verify departure time is in the future

**Weather API Not Working**
- Ensure `OPENWEATHER_API_KEY` is set correctly
- Check your API key quota at OpenWeatherMap dashboard
- Verify key has current weather access enabled

**Slow Mensa Requests**
- First request takes ~20s (Playwright browser startup)
- Subsequent requests are cached for 1 week
- Use `force_refresh=true` to update stale data

**Database Connection Issues**
- API works without database (memory-only caching)
- Check database credentials and network connectivity
- Review logs: `docker logs campus`

### Performance Tips
- Use combined coordinate format: `coords=lat,lon` instead of separate parameters
- Enable database for persistent caching across restarts
- Monitor cache hit rates via `/api/cache/stats`
- Routes are cached for 5 minutes, bikes for 30 seconds

## 🎓 Academic Context

This project was developed for the **Programmierpraktikum at Scalable Software Systems (PP3S)** at TU Berlin, Summer Semester 2025, implementing **Scenario A: The TU Runner** - a campus route planning system.

### Assignment Requirements Met
- ✅ Distributed system (frontend/backend/database)
- ✅ Path finding
- ✅ Intermediate stops support
- ✅ Route storage and caching
- ✅ Pre-calculated route options
- ✅ Location favorites and categories
- ✅ Multiple external APIs (BVG, NextBike, OpenWeather, etc.)
- ✅ Docker containerization
- ✅ Scalability strategy documentation

## 📄 API Documentation

- **Interactive Docs**: http://localhost:8000/docs
- **OpenAPI Schema**: http://localhost:8000/openapi.json
- **Redoc**: http://localhost:8000/redoc

## 📝 License & Contributing

This project is part of academic coursework at TU Berlin. For questions or contributions, please contact the development team.

Contributing
# Fork the repository on GitHub

# Clone your fork
git clone https://github.com/your-username/tu-berlin-campus-router.git

# Create a feature branch
git checkout -b feature/your-feature-name

# Make your changes and test
docker-compose up --build

# Commit and push
git commit -m "Add your feature"
git push origin feature/your-feature-name

# Create a Pull Request on GitHub

Deployment
For production deployment, consider:

Using environment-specific configuration
Setting up proper logging and monitoring
Implementing rate limiting
Using a reverse proxy (nginx)
Database backup strategies

---

**🔗 Quick Links**: [Interactive API Docs](http://localhost:8000/docs) | [Health Check](http://localhost:8000/api/health) | [Cache Stats](http://localhost:8000/api/cache/stats)
