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

        # Удаляем старые записи (старше начала текущей недели)
        await DatabaseService.delete_old_room_schedules(week_start)