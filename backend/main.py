from pathlib import Path
from dotenv import load_dotenv

# Load .env from repository root (local dev). On Render, env vars come from the dashboard.
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    load_dotenv(dotenv_path=_env_path)
else:
    load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routes.demand   import router as demand_router
from backend.routes.iti_supply import router as iti_supply_router
from backend.routes.district import router as district_router
from backend.routes.chat     import router as chat_router
from backend.routes.sectors  import router as sectors_router

app = FastAPI(
    title="Maharashtra Skill Intelligence API",
    description="District-level skill and training intelligence for Maharashtra.",
    version="1.2.0",
)

# CORS — allow GitHub Pages frontend and localhost during development.
# Add your Render URL if you want stricter CORS in production.
ALLOWED_ORIGINS = [
    "https://alpha241026.github.io",   # GitHub Pages
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all route groups
app.include_router(district_router)
app.include_router(sectors_router)
app.include_router(demand_router)
app.include_router(iti_supply_router)
app.include_router(chat_router)


@app.get("/")
def root():
    """Health-check endpoint — confirms API is running."""
    return {"status": "ok", "message": "Maharashtra Skill Intelligence API is running"}
