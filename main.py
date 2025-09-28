from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import sys
import os
import logging
import time
from prometheus_fastapi_instrumentator import Instrumentator

if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from dotenv import load_dotenv
load_dotenv()

from api.endpoints import router as api_router
from utils.api_checker import check_and_update_apis
from providers.RoomSchedule import RoomScheduleProvider
from providers.moses import StudentScheduleProvider
from providers.mensa import MensaProvider
from database.service import DatabaseService

# Логгер
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)



app = FastAPI(title="Mobility Aggregator API")

# Standardized FastAPI Prometheus instrumentation (like Litestar approach)
instrumentator = Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    should_group_untemplated=True,
    excluded_handlers=["/metrics"],
    inprogress_name="http_requests_inprogress",
    inprogress_labels=True,
)

# Instrument the app automatically (like Litestar's built-in approach)
instrumentator.instrument(app).expose(app)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def check_startup_data_freshness():
    """
    Check if we need to update any data on startup using the existing
    missed updates detection logic that checks for complete data coverage.
    """
    try:
        missed_updates = await DatabaseService.check_missed_weekly_updates()

        # Log what we found
        total_missed = sum(missed_updates.values())
        if total_missed > 0:
            logger.info(f"Startup check: {total_missed} systems need updates: {missed_updates}")
        else:
            logger.info("Startup check: All data is fresh and complete")

        return missed_updates

    except Exception as e:
        logger.error(f"Error checking startup data freshness: {e}")
        # Return all True on error to be safe
        return {"rooms": True, "moses": True, "mensa": True}


@app.on_event("startup")
async def startup_background_tasks():
    # Initial check on startup
    try:
        await check_and_update_apis()
    except Exception as e:
        print(f"Initial API check failed: {e}")

    # Check which systems need updates on startup
    missed_updates = await check_startup_data_freshness()

    # Start background updaters (non-blocking) - they'll use the missed_updates info
    asyncio.create_task(background_weekly_room_schedule_updater(missed_updates.get("rooms", True)))

    asyncio.create_task(background_weekly_moses_updater(missed_updates.get("moses", True)))

    asyncio.create_task(background_weekly_mensa_updater(missed_updates.get("mensa", True)))

    # Start background checker
    asyncio.create_task(background_api_checker())

    logger.info("Application startup completed")


async def background_api_checker():
    while True:
        try:
            await asyncio.sleep(600)  # 10 minutes
            await asyncio.wait_for(check_and_update_apis(), timeout=60.0)
        except asyncio.TimeoutError:
            print("API check timed out")
        except Exception as e:
            print(f"API check error: {e}")

async def background_weekly_room_schedule_updater(needs_startup_update: bool = True):
    """
    Background task: update room schedules every week (Monday 00:05) and on startup.
    """
    import datetime

    # Update on startup - using pre-computed freshness check
    if needs_startup_update:
        try:
            logger.info("Room schedules need updating on startup...")
            rooms_json_path = os.getenv("ROOMS_JSON_PATH")
            if not rooms_json_path:
                rooms_json_path = "rooms_id.json"

            # If path is relative, make it relative to script directory
            if not os.path.isabs(rooms_json_path):
                script_dir = os.path.dirname(os.path.abspath(__file__))
                rooms_json_path = os.path.join(script_dir, rooms_json_path)

            # Debug logging
            logger.info(f"Looking for rooms file at: {rooms_json_path}")
            logger.info(f"File exists: {os.path.exists(rooms_json_path)}")

            async with RoomScheduleProvider() as provider:
                await DatabaseService.update_weekly_room_schedules(provider, rooms_json_path)
            logger.info("Room schedules updated on startup (background).")
        except Exception as e:
            logger.error(f"Room schedule update on startup failed: {e}")
    else:
        logger.info("Room schedules are fresh, skipping startup update.")

    # Weekly update schedule
    while True:
        now = datetime.datetime.now()
        # Next Monday 00:05
        next_monday = now + datetime.timedelta(days=(7 - now.weekday()))
        next_run = next_monday.replace(hour=0, minute=5, second=0, microsecond=0)
        sleep_seconds = (next_run - now).total_seconds()
        if sleep_seconds < 0:
            sleep_seconds = 60 * 60 * 24  # fallback: 1 day
        await asyncio.sleep(sleep_seconds)
        try:
            rooms_json_path = os.getenv("ROOMS_JSON_PATH")
            if not rooms_json_path:
                rooms_json_path = "rooms_id.json"

            # If path is relative, make it relative to script directory
            if not os.path.isabs(rooms_json_path):
                script_dir = os.path.dirname(os.path.abspath(__file__))
                rooms_json_path = os.path.join(script_dir, rooms_json_path)
            async with RoomScheduleProvider() as provider:
                await DatabaseService.update_weekly_room_schedules(provider, rooms_json_path)
            logger.info("Room schedules updated by weekly background task.")
        except Exception as e:
            logger.error(f"Weekly room schedule update failed: {e}")

async def background_weekly_moses_updater(needs_startup_update: bool = True):
    """
    Background task: update Moses student schedules every week (Monday 01:05) and on startup.
    """
    import datetime

    # Update on startup - using pre-computed freshness check
    if needs_startup_update:
        try:
            logger.info("Moses schedules need updating on startup...")
            programs_json_path = os.getenv("PROGRAMS_JSON_PATH")
            if not programs_json_path:
                programs_json_path = "program_catalog.json"

            # If path is relative, make it relative to script directory
            if not os.path.isabs(programs_json_path):
                script_dir = os.path.dirname(os.path.abspath(__file__))
                programs_json_path = os.path.join(script_dir, programs_json_path)

            # Debug logging
            logger.info(f"Looking for programs file at: {programs_json_path}")
            logger.info(f"File exists: {os.path.exists(programs_json_path)}")

            async with StudentScheduleProvider() as provider:
                await DatabaseService.update_weekly_moses_schedules(provider, programs_json_path)
            logger.info("Moses schedules updated on startup (background).")
        except Exception as e:
            logger.error(f"Moses schedule update on startup failed: {e}")
    else:
        logger.info("Moses schedules are fresh, skipping startup update.")

    # Weekly update schedule
    while True:
        now = datetime.datetime.now()
        # Next Monday 01:05 (1 hour after rooms)
        next_monday = now + datetime.timedelta(days=(7 - now.weekday()))
        next_run = next_monday.replace(hour=1, minute=5, second=0, microsecond=0)
        sleep_seconds = (next_run - now).total_seconds()
        if sleep_seconds < 0:
            sleep_seconds = 60 * 60 * 24  # fallback: 1 day
        await asyncio.sleep(sleep_seconds)
        try:
            programs_json_path = os.getenv("PROGRAMS_JSON_PATH")
            if not programs_json_path:
                programs_json_path = "program_catalog.json"

            # If path is relative, make it relative to script directory
            if not os.path.isabs(programs_json_path):
                script_dir = os.path.dirname(os.path.abspath(__file__))
                programs_json_path = os.path.join(script_dir, programs_json_path)
            async with StudentScheduleProvider() as provider:
                await DatabaseService.update_weekly_moses_schedules(provider, programs_json_path)
            logger.info("Moses schedules updated by weekly background task.")
        except Exception as e:
            logger.error(f"Weekly Moses schedule update failed: {e}")

async def background_weekly_mensa_updater(needs_startup_update: bool = True):
    """
    Background task: update Mensa menus every week (Monday 02:00) and on startup.
    """
    import datetime

    # Update on startup - using pre-computed freshness check
    if needs_startup_update:
        try:
            logger.info("Mensa menus need updating on startup...")
            async with MensaProvider() as provider:
                await DatabaseService.update_weekly_mensa_menus(provider)
            logger.info("Mensa menus updated on startup (background).")
        except Exception as e:
            logger.error(f"Mensa menu update on startup failed: {e}")
    else:
        logger.info("Mensa menus are fresh, skipping startup update.")

    # Weekly update schedule
    while True:
        now = datetime.datetime.now()
        # Next Monday 02:00 (2 hours after Moses)
        next_monday = now + datetime.timedelta(days=(7 - now.weekday()))
        next_run = next_monday.replace(hour=2, minute=0, second=0, microsecond=0)
        sleep_seconds = (next_run - now).total_seconds()
        if sleep_seconds < 0:
            sleep_seconds = 60 * 60 * 24  # fallback: 1 day
        await asyncio.sleep(sleep_seconds)
        try:
            async with MensaProvider() as provider:
                await DatabaseService.update_weekly_mensa_menus(provider)
            logger.info("Mensa menus updated by weekly background task.")
        except Exception as e:
            logger.error(f"Weekly Mensa menu update failed: {e}")

# Include API routes
app.include_router(api_router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)