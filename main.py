from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import sys
import os
import logging

if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from dotenv import load_dotenv
load_dotenv()

from api.endpoints import router as api_router
from utils.api_checker import check_and_update_apis
from providers.RoomSchedule import RoomScheduleProvider
from database.service import DatabaseService

# Логгер
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Mobility Aggregator API")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup_background_tasks():
    # Initial check on startup
    try:
        await check_and_update_apis()
    except Exception as e:
        print(f"Initial API check failed: {e}")

    # Запускаем обновление расписания комнат как фоновую задачу (не блокирует запуск сервиса)
    asyncio.create_task(background_weekly_room_schedule_updater())

    # Start background checker
    asyncio.create_task(background_api_checker())

async def background_api_checker():
    while True:
        try:
            await asyncio.sleep(600)  # 10 minutes
            await asyncio.wait_for(check_and_update_apis(), timeout=60.0)
        except asyncio.TimeoutError:
            print("API check timed out")
        except Exception as e:
            print(f"API check error: {e}")

async def background_weekly_room_schedule_updater():
    """
    Background task: update room schedules every week (Monday 00:05) и при запуске.
    """
    import datetime

    # --- Обновление при запуске ---
    try:
        rooms_json_path = os.getenv("ROOMS_JSON_PATH", "rooms_id.json")
        async with RoomScheduleProvider() as provider:
            await DatabaseService.update_weekly_room_schedules(provider, rooms_json_path)
        logger.info("Room schedules updated on startup (background).")
    except Exception as e:
        logger.error(f"Room schedule update on startup failed: {e}")

    # --- Периодическое обновление каждую неделю ---
    while True:
        now = datetime.datetime.now()
        # Следующий понедельник 00:05
        next_monday = now + datetime.timedelta(days=(7 - now.weekday()))
        next_run = next_monday.replace(hour=0, minute=5, second=0, microsecond=0)
        sleep_seconds = (next_run - now).total_seconds()
        if sleep_seconds < 0:
            sleep_seconds = 60 * 60 * 24  # fallback: 1 day
        await asyncio.sleep(sleep_seconds)
        try:
            rooms_json_path = os.getenv("ROOMS_JSON_PATH", "rooms_id.json")
            async with RoomScheduleProvider() as provider:
                await DatabaseService.update_weekly_room_schedules(provider, rooms_json_path)
            logger.info("Room schedules updated by weekly background task.")
        except Exception as e:
            logger.error(f"Weekly room schedule update failed: {e}")

# Include API routes
app.include_router(api_router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)