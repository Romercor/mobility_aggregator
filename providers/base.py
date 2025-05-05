from abc import ABC, abstractmethod
from typing import List, Dict, Any
import httpx
class BaseProvider(ABC):
    """Base class for all mobility providers"""
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()