from sqlalchemy import Column, Integer, String, DateTime, JSON, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
import uuid

Base = declarative_base()

class MensaMenu(Base):
    """Mensa menu storage"""
    __tablename__ = "mensa_menus"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mensa_name = Column(String(100), nullable=False, index=True)
    week_start = Column(DateTime, nullable=False)
    menu_data = Column(JSON, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Unique constraint for upsert operations
    __table_args__ = (
        UniqueConstraint('mensa_name', 'week_start', name='uk_mensa_week'),
    )

class StudentSchedule(Base):
    """Student schedule storage"""
    __tablename__ = "student_schedules"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stupo = Column(String(50), nullable=False, index=True)
    semester = Column(Integer, nullable=False, index=True)
    study_program_name = Column(String(200))
    schedule_data = Column(JSON, nullable=False)
    lectures_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Unique constraint for upsert operations
    __table_args__ = (
        UniqueConstraint('stupo', 'semester', name='uk_stupo_semester'),
    )