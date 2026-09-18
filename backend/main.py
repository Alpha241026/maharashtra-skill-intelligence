# import FastAPI class to create the web application
from fastapi import FastAPI

# import demand router containing the "/api/demand" endpoint
from backend.routes.demand import router as demand_router

from backend.routes import iti_supply

from backend.routes import district

from backend.routes import chat

# create main FastAPI application instance for Uvicorn to load and run
app = FastAPI(title="Maharashtra Skill Intelligence API")

# register the demand router with the main FastAPI application
app.include_router(demand_router)

app.include_router(iti_supply.router)

app.include_router(district.router)

app.include_router(chat.router)

# register below function to handle GET requests sent to "/" root path
@app.get("/")
def root():
    """Simple endpoint to verify that the API is running"""

    # return Python dictionary which FastAPI automatically converts into JSON
    return {"message": "Maharashtra Skill Intelligence API is running"}