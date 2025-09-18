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
    request: Request,
    session: SessionDep,
    title: str = Form(...),
    body: str = Form(...),
    category_id: str = Form(...),  # Can be "new" or an actual ID
    subcategory_id: int | None = Form(None),
    platform_choice: list = Form([]),
    ai_platforms: str | None = Form(None),
    suggested_category_name: str | None = Form(None),
    instructions: str | None = Form(None),
    tags: str | None = Form(None)
):
    """Create a new prompt submission"""
    # Handle category selection
    if category_id == "new":
        if not suggested_category_name or suggested_category_name.strip() == "":
            raise HTTPException(status_code=400, detail="Suggested category name is required when selecting 'new category'")
        actual_category_id = None
    else:
        try:
            actual_category_id = int(category_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid category ID")
        suggested_category_name = None
    
    # Handle AI platforms - prefer direct checkbox values over JSON
    platforms = []
    if platform_choice:
        platforms = platform_choice
    elif ai_platforms:
        try:
            if ai_platforms.startswith('['):
                platforms = json.loads(ai_platforms)
            else:
                platforms = [p.strip() for p in ai_platforms.split(',') if p.strip()]
        except (json.JSONDecodeError, AttributeError):
            if ai_platforms:
                platforms = [ai_platforms]
    
    submission = PromptSubmission(
        title=title,
        body=body,
        category_id=actual_category_id,
        subcategory_id=subcategory_id,
        suggested_category_name=suggested_category_name,
        instructions=instructions,
        tags=tags
    )
    
    # Set platforms using the helper method
    if platforms:
        submission.set_platforms(platforms)
    
    session.add(submission)
    session.commit()
    
    # Check if this is an HTMX request
    if request.headers.get("HX-Request"):
        # Return HTML for HTMX
        return HTMLResponse(f"""
        <div class="bg-green-50 border border-green-200 rounded-md p-4">
            <div class="flex">
                <div class="flex-shrink-0">
                    <svg class="h-5 w-5 text-green-400" viewBox="0 0 20 20" fill="currentColor">
                        <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
                    </svg>
                </div>
                <div class="ml-3">
                    <h3 class="text-sm font-medium text-green-800">
                        Submission Successful!
                    </h3>
                    <div class="mt-2 text-sm text-green-700">
                        <p>Your prompt "{title}" has been submitted for review. Our team will review it and add it to the library if approved.</p>
                        {f'<p class="mt-1"><strong>Suggested Category:</strong> {suggested_category_name}</p>' if suggested_category_name else ''}
                    </div>
                </div>
            </div>
        </div>
        """)
    else:
        # Return JSON for API calls
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