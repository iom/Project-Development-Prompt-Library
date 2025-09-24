from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import SQLModel
from app.database import engine
from app.routers import public, admin, auth, htmx
from app.models import *  # Import all models to register them
import os
from pathlib import Path

app = FastAPI(title="IOM Prompt Library", description="A library of prompts for IOM project development")

# Get the base directory - handle both local and Azure paths
base_dir = Path(__file__).parent.parent
static_dir = base_dir / "app" / "static"

# Mount static files with Azure-compatible path
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
else:
    print(f"Warning: Static directory not found at {static_dir}")

# Health check endpoint for Azure
@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "IOM Prompt Library"}

# Templates - Azure-compatible path
template_dir = base_dir / "app" / "templates"
templates = Jinja2Templates(directory=str(template_dir))

# Include routers
app.include_router(public.router)
app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(htmx.router)

# Create tables on startup
@app.on_event("startup")
def create_db_and_tables():
    try:
        print("Creating database tables...")
        SQLModel.metadata.create_all(engine)
        print("Database tables created successfully")
        
        # Run database migrations
        _run_migrations()
        
        # Check if database is empty and load seed data
        from sqlmodel import Session, select
    from sqlalchemy import func
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
            
            # Load seed data - try multiple possible paths
            seed_paths = [
                Path("seed/prompts_seed.json"),
                base_dir / "seed" / "prompts_seed.json",
                Path("/home/site/wwwroot/seed/prompts_seed.json")
            ]
            
            seed_file = None
            for path in seed_paths:
                if path.exists():
                    seed_file = path
                    break
            
            if seed_file:
                print(f"Loading seed data from {seed_file}")
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
                            # Get next sort_order for seeded category
                            max_sort_order = session.exec(
                                select(func.max(Category.sort_order))
                            ).first()
                            next_sort_order = (max_sort_order or 0) + 1
                            
                            new_cat = Category(
                                name=category_name,
                                slug=slugify(category_name),
                                description=f"Category for {category_name} prompts",
                                sort_order=next_sort_order
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
    except Exception as e:
        print(f"Error during database initialization: {e}")
        # Don't fail startup completely, just log the error

def _run_migrations():
    """Run database migrations"""
    from sqlmodel import Session, text
    import sqlite3
    
    try:
        with Session(engine) as session:
            # Check table structure
            result = session.exec(text("PRAGMA table_info(promptsubmission)")).all()
            columns = {row[1]: row for row in result}  # {column_name: (cid, name, type, notnull, default, pk)}
            
            # Migration 1: Add suggested_category_name column if missing
            if 'suggested_category_name' not in columns:
                print("Adding suggested_category_name column to promptsubmission table...")
                session.exec(text("ALTER TABLE promptsubmission ADD COLUMN suggested_category_name TEXT"))
                session.commit()
                print("Migration 1 completed: suggested_category_name column added")
            
            # Migration 2: Add sort_order column to category table if missing
            category_result = session.exec(text("PRAGMA table_info(category)")).all()
            category_columns = {row[1]: row for row in category_result}
            
            if 'sort_order' not in category_columns:
                print("Adding sort_order column to category table...")
                session.exec(text("ALTER TABLE category ADD COLUMN sort_order INTEGER DEFAULT 0"))
                
                # Set initial sort_order values based on current ID order
                session.exec(text("""
                    UPDATE category 
                    SET sort_order = id 
                    WHERE sort_order = 0
                """))
                session.commit()
                print("Migration completed: sort_order column added to category table")
            
            # Migration 3: Fix category_id to allow NULL values
            if 'category_id' in columns and columns['category_id'][3] == 1:  # notnull == 1 means NOT NULL
                print("Fixing category_id column to allow NULL values...")
                
                # SQLite doesn't support ALTER COLUMN, so we need to recreate the table
                session.exec(text("""
                    CREATE TABLE promptsubmission_temp (
                        id INTEGER PRIMARY KEY,
                        title TEXT NOT NULL,
                        body TEXT NOT NULL,
                        category_id INTEGER,
                        subcategory_id INTEGER,
                        ai_platforms TEXT,
                        instructions TEXT,
                        tags TEXT,
                        suggested_category_name TEXT,
                        status TEXT NOT NULL DEFAULT 'pending',
                        submitted_by INTEGER,
                        reviewer_notes TEXT,
                        approved_prompt_id INTEGER,
                        created_at TEXT NOT NULL,
                        reviewed_at TEXT,
                        FOREIGN KEY (category_id) REFERENCES category(id),
                        FOREIGN KEY (subcategory_id) REFERENCES category(id),
                        FOREIGN KEY (submitted_by) REFERENCES user(id),
                        FOREIGN KEY (approved_prompt_id) REFERENCES prompt(id)
                    )
                """))
                
                # Copy existing data
                session.exec(text("""
                    INSERT INTO promptsubmission_temp 
                    SELECT id, title, body, category_id, subcategory_id, ai_platforms, 
                           instructions, tags, suggested_category_name, status, submitted_by, 
                           reviewer_notes, approved_prompt_id, created_at, reviewed_at
                    FROM promptsubmission
                """))
                
                # Replace old table
                session.exec(text("DROP TABLE promptsubmission"))
                session.exec(text("ALTER TABLE promptsubmission_temp RENAME TO promptsubmission"))
                
                session.commit()
                print("Migration 3 completed: category_id now allows NULL values")
            else:
                print("Database schema is up to date")
                
    except Exception as e:
        print(f"Migration warning: {e}")
        # Don't fail startup if migration has issues

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("library.html", {"request": request})