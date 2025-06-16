from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_
from sqlalchemy.dialects.postgresql import insert
import logging

from database.models import MensaMenu, StudentSchedule
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