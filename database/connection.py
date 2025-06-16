import os
import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy import text
from database.models import Base
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    """async database manager"""
    
    def __init__(self):
        self.engine = None
        self.async_session_maker = None
        self._initialized = False
    
    def get_database_url(self) -> str:
        """Construct database URL from environment variables"""
        host = os.getenv("DB_HOST", "localhost")
        port = os.getenv("DB_PORT", "5432")
        database = os.getenv("DB_NAME", "campus_router")
        user = os.getenv("DB_USER", "campus_user")
        password = os.getenv("DB_PASSWORD", "campus_pass")
        
        return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{database}"
    
    async def initialize(self):
        """Initialize database connection and create tables"""
        if self._initialized:
            return
        
        try:
            database_url = self.get_database_url()
            logger.info(f"Connecting to database: {database_url.split('@')[1]}")
            
            # Create async engine
            self.engine = create_async_engine(
                database_url,
                poolclass=NullPool,
                echo=False,
                future=True
            )
            
            # Create session maker
            self.async_session_maker = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Test connection
            await self.test_connection()
            
            # Create tables if they don't exist
            await self.create_tables()
            
            self._initialized = True
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {str(e)}")
            raise
    
    async def test_connection(self):
        """Test database connection"""
        try:
            async with self.engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Database connection test successful")
        except Exception as e:
            logger.error(f"Database connection test failed: {str(e)}")
            raise
    
    async def create_tables(self):
        """Create all tables"""
        try:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            logger.info("All tables created successfully")
        except Exception as e:
            logger.error(f"Table creation failed: {str(e)}")
            raise
    
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get async database session"""
        if not self._initialized:
            await self.initialize()
        
        async with self.async_session_maker() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def close(self):
        """Close database connections"""
        if self.engine:
            await self.engine.dispose()
            logger.info("Database connections closed")

# Global database manager instance
db_manager = DatabaseManager()

# Convenience function for getting database sessions
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session - use this in your code"""
    async for session in db_manager.get_session():
        yield session

async def check_database_health() -> dict:
    """database health check"""
    try:
        if not db_manager._initialized:
            await db_manager.initialize()
        
        async for session in db_manager.get_session():
            # Simple test query
            result = await session.execute(text("SELECT 1 as test"))
            test_result = result.fetchone()
            
            return {
                "status": "healthy" if test_result[0] == 1 else "unhealthy",
                "initialized": db_manager._initialized
            }
            break
            
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "initialized": db_manager._initialized
        }