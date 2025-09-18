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
    
    
    # Check if database is empty and load seed data
    from sqlmodel import Session, select
    from app.models import Category, Prompt
    import json
    import os
    from pathlib import Path
    from slugify import slugify
    
    with Session(engine) as session:
        # Check if we have any categories
        categories_count = len(session.exec(select(Category)).all())
        
        if categories_count == 0:
            print("Database is empty. Loading seed data...")
            
            # Load seed data
            seed_file = Path("seed/prompts_seed.json")
            if seed_file.exists():
                with open(seed_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                category_cache = {}
                
                for item in data:
                    category_name = item.get('category', '').strip()
                    if not category_name:
                        continue
                    
                    # Get or create category
                    if category_name not in category_cache:
                        existing_cat = session.exec(
                            select(Category).where(Category.name == category_name)
                        ).first()
                        
                        if existing_cat:
                            category_cache[category_name] = existing_cat
                        else:
                            new_cat = Category(
                                name=category_name,
                                slug=slugify(category_name),
                                description=f"Category for {category_name} prompts"
                            )
                            session.add(new_cat)
                            session.commit()
                            session.refresh(new_cat)
                            category_cache[category_name] = new_cat
                    
                    category = category_cache[category_name]
                    
                    # Check if prompt already exists
                    existing_prompt = session.exec(
                        select(Prompt).where(
                            Prompt.title == item['title'],
                            Prompt.category_id == category.id
                        )
                    ).first()
                    
                    if existing_prompt:
                        continue
                    
                    # Create the prompt
                    prompt = Prompt(
                        title=item['title'],
                        body=item['body'],
                        category_id=category.id,
                        status=item.get('status', 'published'),
                        tags=','.join(item.get('tags', [])) if item.get('tags') else None
                    )
                    
                    session.add(prompt)
                
                session.commit()
                print(f"Loaded {len(data)} prompts into the database")
            else:
                print("Seed file not found, skipping seed data loading")

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("library.html", {"request": request})