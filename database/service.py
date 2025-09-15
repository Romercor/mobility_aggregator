from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
from sqlalchemy.dialects.postgresql import insert
import logging

from database.models import MensaMenu, StudentSchedule, RoomSchedule
from database.connection import get_db_session
from api.models import WeeklyMenu, StudentLecture

logger = logging.getLogger(__name__)

class DatabaseService:
    """service for database operations"""
    
    @staticmethod
    async def save_mensa_menu(menu: WeeklyMenu, force_update: bool = False) -> bool:
        """
        Save mensa menu to database with upsert
        
        Args:
            menu: WeeklyMenu object to save
            force_update: Force update even if recent data exists
            
        Returns:
            True if saved/updated, False if failed
        """
        try:
            async for session in get_db_session():
                # Calculate week start (Monday)
                now = datetime.now()
                week_start = now - timedelta(days=now.weekday())
                week_start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
                
                # Prepare menu data for JSON storage
                menu_data = {
                    "mensa_name": menu.mensa_name,
                    "last_updated": menu.last_updated.isoformat(),
                    "days": [
                        {
                            "day_name": day.day_name,
                            "is_available": day.is_available,
                            "groups": {
                                group_name: [
                                    {
                                        "name": dish.name,
                                        "price": dish.price,
                                        "vegan": dish.vegan,
                                        "vegetarian": dish.vegetarian
                                    }
                                    for dish in dishes
                                ]
                                for group_name, dishes in day.groups.items()
                            }
                        }
                        for day in menu.days
                    ]
                }
                
                # Use upsert (INSERT ... ON CONFLICT UPDATE)
                stmt = insert(MensaMenu).values(
                    mensa_name=menu.mensa_name,
                    week_start=week_start,
                    menu_data=menu_data,
                    last_updated=datetime.now()
                )
                
                # On conflict, update the data
                stmt = stmt.on_conflict_do_update(
                    index_elements=['mensa_name', 'week_start'],
                    set_={
                        'menu_data': stmt.excluded.menu_data,
                        'last_updated': stmt.excluded.last_updated
                    }
                )
                
                await session.execute(stmt)
                await session.commit()
                
                logger.info(f"Saved menu for {menu.mensa_name}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to save menu for {menu.mensa_name}: {str(e)}")
            return False
    
    @staticmethod
    async def save_student_schedule(
        stupo: str, 
        semester: int, 
        lectures: List[StudentLecture], 
        study_program_name: Optional[str] = None,
        force_update: bool = False
    ) -> bool:
        """
        Save student schedule to database with upsert
        
        Args:
            stupo: Studienordnung identifier
            semester: Semester number
            lectures: List of lectures
            study_program_name: Optional program name
            force_update: Force update even if recent data exists
            
        Returns:
            True if saved/updated, False if failed
        """
        try:
            async for session in get_db_session():
                # Prepare lecture data for JSON storage
                schedule_data = [
                    {
                        "course_name": lecture.course_name,
                        "instructor": lecture.instructor,
                        "location": lecture.location,
                        "time_schedule": lecture.time_schedule
                    }
                    for lecture in lectures
                ]
                
                # Use upsert (INSERT ... ON CONFLICT UPDATE)
                stmt = insert(StudentSchedule).values(
                    stupo=stupo,
                    semester=semester,
                    study_program_name=study_program_name,
                    schedule_data=schedule_data,
                    lectures_count=len(lectures),
                    last_updated=datetime.now()
                )
                
                # On conflict, update the data
                stmt = stmt.on_conflict_do_update(
                    index_elements=['stupo', 'semester'],
                    set_={
                        'study_program_name': stmt.excluded.study_program_name,
                        'schedule_data': stmt.excluded.schedule_data,
                        'lectures_count': stmt.excluded.lectures_count,
                        'last_updated': stmt.excluded.last_updated
                    }
                )
                
                await session.execute(stmt)
                await session.commit()
                
                logger.info(f"Saved schedule for {stupo}:{semester} ({len(lectures)} lectures)")
                return True
                
        except Exception as e:
            logger.error(f"Failed to save schedule for {stupo}:{semester}: {str(e)}")
            return False
    
    @staticmethod
    async def get_mensa_menu(mensa_name: str) -> Optional[Dict[str, Any]]:
        """Get latest mensa menu from database"""
        try:
            #print(f"DEBUG: Searching for mensa_name='{mensa_name}'")
            async for session in get_db_session():
                result = await session.execute(
                    select(MensaMenu)
                    .where(MensaMenu.mensa_name == mensa_name)
                    .order_by(desc(MensaMenu.last_updated))
                    .limit(1)
                )
                menu_record = result.fetchone()
                #print(f"DEBUG: Query result: {menu_record is not None}")
                
                if menu_record:
                    #print(f"DEBUG: Found menu for '{menu_record[0].mensa_name}'")
                    return menu_record[0].menu_data
                else:
                    #print(f"DEBUG: No menu found for '{mensa_name}'")
                    return None
                    
        except Exception as e:
            print(f"DEBUG: Database error: {str(e)}")
            logger.error(f"Failed to get menu for {mensa_name}: {str(e)}")
            return None
    
    @staticmethod
    async def get_student_schedule(stupo: str, semester: int) -> Optional[Dict[str, Any]]:
        """Get latest student schedule from database"""
        try:
            async for session in get_db_session():
                result = await session.execute(
                    select(StudentSchedule)
                    .where(
                        and_(
                            StudentSchedule.stupo == stupo,
                            StudentSchedule.semester == semester
                        )
                    )
                    .order_by(desc(StudentSchedule.last_updated))
                    .limit(1)
                )
                schedule_record = result.fetchone()
                
                if schedule_record:
                    record = schedule_record[0]
                    return {
                        "stupo": record.stupo,
                        "semester": record.semester,
                        "study_program_name": record.study_program_name,
                        "schedule_data": record.schedule_data,
                        "lectures_count": record.lectures_count,
                        "last_updated": record.last_updated.isoformat()
                    }
                return None
                
        except Exception as e:
            logger.error(f"Failed to get schedule for {stupo}:{semester}: {str(e)}")
            return None
    
    @staticmethod
    async def save_room_schedule(room_id: str, date: datetime, schedule_data: list) -> bool:
        """
        Save room schedule for a specific day (upsert).
        """
        try:
            async for session in get_db_session():
                stmt = insert(RoomSchedule).values(
                    room_id=room_id,
                    date=date,
                    schedule_data=schedule_data,
                    last_updated=datetime.now()
                )
                stmt = stmt.on_conflict_do_update(
                    index_elements=['room_id', 'date'],
                    set_={
                        'schedule_data': stmt.excluded.schedule_data,
                        'last_updated': stmt.excluded.last_updated
                    }
                )
                await session.execute(stmt)
                await session.commit()
                logger.info(f"Saved room schedule for {room_id} on {date.date()}")
                return True
        except Exception as e:
            logger.error(f"Failed to save room schedule for {room_id} on {date.date()}: {str(e)}")
            return False

    @staticmethod
    async def get_room_schedule(room_id: str, date: datetime) -> Optional[dict]:
        """
        Get room schedule for a specific day.
        """
        try:
            async for session in get_db_session():
                result = await session.execute(
                    select(RoomSchedule)
                    .where(
                        (RoomSchedule.room_id == room_id) &
                        (RoomSchedule.date == date)
                    )
                    .order_by(desc(RoomSchedule.last_updated))
                    .limit(1)
                )
                record = result.fetchone()
                if record:
                    return record[0].schedule_data
                return None
        except Exception as e:
            logger.error(f"Failed to get room schedule for {room_id} on {date.date()}: {str(e)}")
            return None

    @staticmethod
    async def delete_old_room_schedules(before_date: datetime) -> int:
        """
        Delete all room schedules older than before_date.
        Returns number of deleted rows.
        """
        try:
            async for session in get_db_session():
                result = await session.execute(
                    RoomSchedule.__table__.delete().where(RoomSchedule.date < before_date)
                )
                await session.commit()
                logger.info(f"Deleted old room schedules before {before_date.date()}")
                return result.rowcount if hasattr(result, "rowcount") else 0
        except Exception as e:
            logger.error(f"Failed to delete old room schedules: {str(e)}")
            return 0

    @staticmethod
    async def update_weekly_room_schedules(provider, rooms_json_path: str):
        """
        Update all room schedules for the current week for all rooms in rooms_json_path.
        """
        import json
        from datetime import timedelta

        # Определяем текущую неделю (понедельник-воскресенье)
        today = datetime.now()
        week_start = today - timedelta(days=today.weekday())
        week_dates = [week_start + timedelta(days=i) for i in range(7)]

        # Загружаем id комнат
        with open(rooms_json_path, "r") as f:
            room_ids = json.load(f)

        for room_id_num in room_ids:
            room_id = f"raum{room_id_num}"
            for date in week_dates:
                date_str = date.strftime("%Y-%m-%d")
                try:
                    schedule = await provider.get_room_schedule(room_id, date_str)
                    await DatabaseService.save_room_schedule(room_id, date.replace(hour=0, minute=0, second=0, microsecond=0), schedule)
                except Exception as e:
                    logger.error(f"Failed to update schedule for {room_id} on {date_str}: {str(e)}")

        # Delete old records (older than current week start)
        await DatabaseService.delete_old_room_schedules(week_start)

    @staticmethod
    async def update_weekly_moses_schedules(provider, programs_json_path: str):
        """
        Update all Moses student schedules for all programs in programs_json_path.
        Only updates stale data (>14 days old).
        """
        import json
        from datetime import timedelta
        
        logger.info("Starting Moses bulk schedule update...")
        
        # Load program catalog
        with open(programs_json_path, "r", encoding="utf-8") as f:
            programs = json.load(f)
            
        successful_updates = 0
        failed_updates = 0
        skipped_updates = 0
        
        for program in programs:
            program_code = str(program["program_code"])
            program_name = program["program_name"]  # Use friendly name from catalog
            
            # Determine semester range based on degree type
            is_master = "Master" in program_name
            max_semester = 4 if is_master else 6
            
            for semester in range(1, max_semester + 1):
                try:
                    # Check if data is stale before scraping
                    cache_key = f"lectures_with_info:{program_code}:{semester}:True"
                    
                    # Check database for existing data
                    existing_data = await DatabaseService.get_student_schedule(program_code, semester)
                    should_update = True
                    
                    if existing_data:
                        # Use existing refresh logic from Moses provider
                        last_updated = existing_data.get("last_updated")
                        if isinstance(last_updated, str):
                            from datetime import datetime
                            last_updated = datetime.fromisoformat(last_updated)
                        
                        if last_updated and (datetime.now() - last_updated).days < 14:
                            should_update = False
                            skipped_updates += 1
                            continue
                    
                    if should_update:
                        # Scrape fresh data
                        lectures, scraped_program_name = await provider.get_student_lectures_with_program_info(
                            program_code, semester, filter_dates=True
                        )
                        
                        # Use catalog name as fallback if Moses extraction fails
                        final_program_name = scraped_program_name or program_name
                        
                        # Save to database (this will bypass cache)
                        if lectures or final_program_name:
                            saved = await DatabaseService.save_student_schedule(
                                program_code, semester, lectures, final_program_name
                            )
                            if saved:
                                successful_updates += 1
                                logger.info(f"Updated {program_code} ({final_program_name}) semester {semester}: {len(lectures)} lectures")
                            else:
                                failed_updates += 1
                        else:
                            skipped_updates += 1
                            
                except Exception as e:
                    failed_updates += 1
                    logger.error(f"Failed to update {program_code} semester {semester}: {str(e)}")
        
        # Delete old Moses schedules (older than 30 days)
        cleanup_date = datetime.now() - timedelta(days=30)
        deleted_count = await DatabaseService.delete_old_moses_schedules(cleanup_date)
        
        logger.info(f"Moses bulk update completed: {successful_updates} updated, {skipped_updates} skipped, {failed_updates} failed, {deleted_count} old records cleaned")

    @staticmethod
    async def update_weekly_mensa_menus(provider):
        """
        Update all Mensa weekly menus for all available mensas.
        Much simpler than Moses - only 3 locations.
        """
        logger.info("Starting Mensa bulk menu update...")
        
        # Get all available mensas
        mensa_names = provider.get_available_mensas()
        
        successful_updates = 0
        failed_updates = 0
        
        for mensa_name in mensa_names:
            try:
                # Get weekly menu (uses existing cache-first logic)
                weekly_menu = await provider.get_weekly_menu(mensa_name, force_refresh=True)
                
                if weekly_menu:
                    # Save to database
                    saved = await DatabaseService.save_mensa_menu(weekly_menu, force_update=True)
                    if saved:
                        successful_updates += 1
                        logger.info(f"Updated {mensa_name} menu")
                    else:
                        failed_updates += 1
                        logger.error(f"Failed to save {mensa_name} menu to database")
                else:
                    failed_updates += 1
                    logger.error(f"No menu data retrieved for {mensa_name}")
                    
            except Exception as e:
                failed_updates += 1
                logger.error(f"Failed to update {mensa_name} menu: {str(e)}")
        
        # Delete old Mensa menus (older than 14 days)
        cleanup_date = datetime.now() - timedelta(days=14)
        deleted_count = await DatabaseService.delete_old_mensa_menus(cleanup_date)
        
        logger.info(f"Mensa bulk update completed: {successful_updates} updated, {failed_updates} failed, {deleted_count} old records cleaned")

    @staticmethod
    async def check_missed_weekly_updates() -> Dict[str, bool]:
        """
        Check if we missed any scheduled weekly updates.
        Returns dict indicating which systems need updates.
        """
        from datetime import datetime, timedelta
        
        now = datetime.now()
        current_week_monday = now - timedelta(days=now.weekday())
        current_week_monday = current_week_monday.replace(hour=0, minute=0, second=0, microsecond=0)
        
        missed_updates = {
            "rooms": False,
            "moses": False, 
            "mensa": False
        }
        
        try:
            # Check if we're past the scheduled times this week
            room_schedule_time = current_week_monday.replace(hour=0, minute=5)
            moses_schedule_time = current_week_monday.replace(hour=1, minute=5)
            mensa_schedule_time = current_week_monday.replace(hour=2, minute=0)
            
            # Only check if we're past the scheduled time
            if now < room_schedule_time:
                return missed_updates  # Too early in the week
            
            # Check Rooms - look for any room data from this week
            if now >= room_schedule_time:
                async for session in get_db_session():
                    result = await session.execute(
                        select(RoomSchedule)
                        .where(RoomSchedule.last_updated >= current_week_monday)
                        .limit(1)
                    )
                    room_data = result.fetchone()
                    if not room_data:
                        missed_updates["rooms"] = True
                        logger.info(f"Missed room update detected - no data since {current_week_monday}")
            
            # Check Moses - look for any Moses data from this week
            if now >= moses_schedule_time:
                async for session in get_db_session():
                    result = await session.execute(
                        select(StudentSchedule)
                        .where(StudentSchedule.last_updated >= current_week_monday)
                        .limit(1)
                    )
                    moses_data = result.fetchone()
                    if not moses_data:
                        missed_updates["moses"] = True
                        logger.info(f"Missed Moses update detected - no data since {current_week_monday}")
            
            # Check Mensa - look for any Mensa data from this week
            if now >= mensa_schedule_time:
                async for session in get_db_session():
                    result = await session.execute(
                        select(MensaMenu)
                        .where(MensaMenu.last_updated >= current_week_monday)
                        .limit(1)
                    )
                    mensa_data = result.fetchone()
                    if not mensa_data:
                        missed_updates["mensa"] = True
                        logger.info(f"Missed Mensa update detected - no data since {current_week_monday}")
                        
        except Exception as e:
            logger.error(f"Error checking missed updates: {str(e)}")
            # Assume all missed on error to be safe
            missed_updates = {"rooms": True, "moses": True, "mensa": True}
        
        total_missed = sum(missed_updates.values())
        if total_missed > 0:
            logger.warning(f"Detected {total_missed} missed weekly updates: {missed_updates}")
        else:
            logger.info("No missed weekly updates detected")
            
        return missed_updates

    @staticmethod
    async def delete_old_moses_schedules(before_date: datetime) -> int:
        """
        Delete all Moses student schedules older than before_date.
        Returns number of deleted rows.
        """
        try:
            async for session in get_db_session():
                result = await session.execute(
                    StudentSchedule.__table__.delete().where(StudentSchedule.last_updated < before_date)
                )
                await session.commit()
                logger.info(f"Deleted old Moses schedules before {before_date.date()}")
                return result.rowcount if hasattr(result, "rowcount") else 0
        except Exception as e:
            logger.error(f"Failed to delete old Moses schedules: {str(e)}")
            return 0

    @staticmethod
    async def delete_old_mensa_menus(before_date: datetime) -> int:
        """
        Delete all Mensa menus older than before_date.
        Returns number of deleted rows.
        """
        try:
            async for session in get_db_session():
                result = await session.execute(
                    MensaMenu.__table__.delete().where(MensaMenu.last_updated < before_date)
                )
                await session.commit()
                logger.info(f"Deleted old Mensa menus before {before_date.date()}")
                return result.rowcount if hasattr(result, "rowcount") else 0
        except Exception as e:
            logger.error(f"Failed to delete old Mensa menus: {str(e)}")
            return 0