from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import sys
if sys.platform.startswith('win'):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from dotenv import load_dotenv
load_dotenv()

from api.endpoints import router as api_router
from utils.api_checker import check_and_update_apis

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

# Include API routes
app.include_router(api_router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)