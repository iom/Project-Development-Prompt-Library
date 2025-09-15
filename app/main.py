from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import SQLModel
from app.database import engine
from app.routers import public, admin, auth, htmx
from app.models import *  # Import all models to register them

app = FastAPI(title="IOM Prompt Library", description="A library of prompts for IOM project development")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Templates
templates = Jinja2Templates(directory="app/templates")

# Include routers
app.include_router(public.router)
app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(htmx.router)

# Create tables on startup
@app.on_event("startup")
def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("library.html", {"request": request})