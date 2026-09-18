from pathlib import Path
from dotenv import load_dotenv

# Load .env file from repository root or current directory
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path)
else:
    load_dotenv()

# import FastAPI class to create the web application
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# import routers
from backend.routes.demand import router as demand_router
from backend.routes import iti_supply
from backend.routes import district
from backend.routes import chat

# create main FastAPI application instance for Uvicorn to load and run
app = FastAPI(title="Maharashtra Skill Intelligence API")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# register the routers with the main FastAPI application
app.include_router(demand_router)
app.include_router(iti_supply.router)
app.include_router(district.router)
app.include_router(chat.router)


# register below function to handle GET requests sent to "/" root path
@app.get("/")
def root():
    """Simple endpoint to verify that the API is running"""
    return {"message": "Maharashtra Skill Intelligence API is running"}
