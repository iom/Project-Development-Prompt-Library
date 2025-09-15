from fastapi import APIRouter, Depends, Query, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlmodel import select, or_, col
from app.database import SessionDep
from app.models import Prompt, Category, PromptSubmission
from typing import List, Dict, Any
import json

router = APIRouter(tags=["public"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/api/prompts")
def list_prompts(
    session: SessionDep, 
    query: str = "", 
    category: int | None = None,
    platform: str | None = None, 
    page: int = 1, 
    page_size: int = 20
):
    """List prompts with search and filtering"""
    stmt = select(Prompt).where(Prompt.status == "published")
    
    if query:
        like = f"%{query}%"
        stmt = stmt.where(
            or_(
                col(Prompt.title).ilike(like),
                col(Prompt.body).ilike(like),
                col(Prompt.instructions).ilike(like)
            )
        )
    
    if category:
        stmt = stmt.where(
            or_(
                Prompt.category_id == category,
                Prompt.subcategory_id == category
            )
        )
    
    if platform:
        stmt = stmt.where(Prompt.ai_platform == platform)
    
    prompts = session.exec(stmt).all()
    
    # Simple pagination
    total = len(prompts)
    start = (page - 1) * page_size
    items = prompts[start:start + page_size]
    
    return {
        "items": items,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": (total + page_size - 1) // page_size
    }

@router.get("/api/prompts/{prompt_id}")
def get_prompt(prompt_id: int, session: SessionDep):
    """Get single prompt detail"""
    prompt = session.get(Prompt, prompt_id)
    if not prompt or prompt.status != "published":
        raise HTTPException(status_code=404, detail="Prompt not found")
    return prompt

@router.get("/api/categories")
def list_categories(session: SessionDep):
    """List all categories"""
    categories = session.exec(select(Category)).all()
    return categories

@router.post("/api/submissions")
def create_submission(
    session: SessionDep,
    title: str = Form(...),
    body: str = Form(...),
    category_id: int = Form(...),
    subcategory_id: int | None = Form(None),
    ai_platform: str | None = Form(None),
    instructions: str | None = Form(None),
    tags: str | None = Form(None)
):
    """Create a new prompt submission"""
    submission = PromptSubmission(
        title=title,
        body=body,
        category_id=category_id,
        subcategory_id=subcategory_id,
        ai_platform=ai_platform,
        instructions=instructions,
        tags=tags
    )
    session.add(submission)
    session.commit()
    return {"message": "Submission created successfully", "id": submission.id}

@router.get("/prompt/{prompt_id}", response_class=HTMLResponse)
async def prompt_detail(request: Request, prompt_id: int, session: SessionDep):
    """Prompt detail page"""
    prompt = session.get(Prompt, prompt_id)
    if not prompt or prompt.status != "published":
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    # Get category info
    category = session.get(Category, prompt.category_id)
    subcategory = None
    if prompt.subcategory_id:
        subcategory = session.get(Category, prompt.subcategory_id)
    
    return templates.TemplateResponse(
        "prompt_detail.html",
        {
            "request": request,
            "prompt": prompt,
            "category": category,
            "subcategory": subcategory
        }
    )

@router.get("/submit", response_class=HTMLResponse)
async def submit_form(request: Request, session: SessionDep):
    """Submit prompt form"""
    categories = session.exec(select(Category).where(col(Category.parent_id).is_(None))).all()
    return templates.TemplateResponse(
        "submit.html",
        {"request": request, "categories": categories}
    )