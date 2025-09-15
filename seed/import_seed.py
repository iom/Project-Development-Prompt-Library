#!/usr/bin/env python3
"""
Import seed data from JSON file into the database
"""
import sys
import os
import json
from pathlib import Path
from slugify import slugify

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlmodel import Session, select, SQLModel
from app.database import engine
from app.models import Category, Prompt

def import_seed_data():
    """Import the seed data from JSON file"""
    seed_file = Path(__file__).parent / "prompts_seed.json"
    
    if not seed_file.exists():
        print(f"Seed file not found: {seed_file}")
        return
    
    # Create all tables
    print("Creating database tables...")
    SQLModel.metadata.create_all(engine)
    
    print(f"Loading seed data from {seed_file}")
    with open(seed_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    with Session(engine) as session:
        # Track categories we've created
        category_cache = {}
        
        print(f"Processing {len(data)} prompts...")
        
        for item in data:
            category_name = item.get('category', '').strip()
            if not category_name:
                print(f"Skipping prompt without category: {item.get('title', 'Unknown')}")
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
                    print(f"Created category: {category_name}")
            
            category = category_cache[category_name]
            
            # Check if prompt already exists (by title and category)
            existing_prompt = session.exec(
                select(Prompt).where(
                    Prompt.title == item['title'],
                    Prompt.category_id == category.id
                )
            ).first()
            
            if existing_prompt:
                print(f"Skipping existing prompt: {item['title']}")
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
            print(f"Added prompt: {item['title']}")
        
        session.commit()
        print("Seed data import completed successfully!")

if __name__ == "__main__":
    import_seed_data()