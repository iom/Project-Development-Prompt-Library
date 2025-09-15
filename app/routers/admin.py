from fastapi import APIRouter, Depends, HTTPException, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlmodel import select
from app.database import SessionDep
from app.models import PromptSubmission, Prompt, Category, AuditLog
from datetime import datetime
import json

router = APIRouter(prefix="/admin", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")

# Temporary admin authentication (to be replaced with Replit Auth)
def admin_required(request: Request):
    """Temporary admin check - replace with proper auth later"""
    import os
    # Use environment variable for admin key (better than hardcoded)
    required_key = os.getenv("ADMIN_KEY", "change-me-in-production")
    admin_key = request.headers.get("X-Admin-Key")
    if admin_key != required_key:
        raise HTTPException(status_code=403, detail="Admin access required")
    return {"admin": True}

@router.get("/api/submissions")
def list_submissions(session: SessionDep, status: str = "pending", admin=Depends(admin_required)):
    """List prompt submissions for review"""
    submissions = session.exec(
        select(PromptSubmission).where(PromptSubmission.status == status)
    ).all()
    return submissions

@router.patch("/api/submissions/{submission_id}")
def review_submission(
    submission_id: int,
    session: SessionDep,
    status: str = Form(...),  # 'approved' or 'rejected'
    reviewer_notes: str = Form(""),
    admin=Depends(admin_required)
):
    """Approve or reject a submission"""
    submission = session.get(PromptSubmission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    
    if status not in ["approved", "rejected"]:
        raise HTTPException(status_code=400, detail="Invalid status")
    
    submission.status = status
    submission.reviewer_notes = reviewer_notes
    submission.reviewed_at = datetime.utcnow()
    
    # If approved, create a prompt
    if status == "approved":
        prompt = Prompt(
            title=submission.title,
            body=submission.body,
            category_id=submission.category_id,
            subcategory_id=submission.subcategory_id,
            ai_platform=submission.ai_platform,
            instructions=submission.instructions,
            tags=submission.tags,
            status="published",
            created_by=submission.submitted_by
        )
        session.add(prompt)
        session.commit()
        session.refresh(prompt)
        
        submission.approved_prompt_id = prompt.id
    
    session.add(submission)
    session.commit()
    
    return {"message": f"Submission {status} successfully"}

@router.get("/api/prompts")
def list_admin_prompts(session: SessionDep, admin=Depends(admin_required)):
    """List all prompts for admin management"""
    prompts = session.exec(select(Prompt)).all()
    return prompts

@router.patch("/api/prompts/{prompt_id}")
def update_prompt(
    prompt_id: int,
    session: SessionDep,
    admin=Depends(admin_required),
    title: str = Form(None),
    body: str = Form(None),
    status: str = Form(None),
    category_id: int = Form(None),
    subcategory_id: int = Form(None),
    ai_platform: str = Form(None),
    instructions: str = Form(None),
    tags: str = Form(None)
):
    """Update a prompt"""
    prompt = session.get(Prompt, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    if title is not None:
        prompt.title = title
    if body is not None:
        prompt.body = body
    if status is not None:
        prompt.status = status
    if category_id is not None:
        prompt.category_id = category_id
    if subcategory_id is not None:
        prompt.subcategory_id = subcategory_id
    if ai_platform is not None:
        prompt.ai_platform = ai_platform
    if instructions is not None:
        prompt.instructions = instructions
    if tags is not None:
        prompt.tags = tags
    
    prompt.updated_at = datetime.utcnow()
    session.add(prompt)
    session.commit()
    
    return {"message": "Prompt updated successfully"}

@router.delete("/api/prompts/{prompt_id}")
def delete_prompt(prompt_id: int, session: SessionDep, admin=Depends(admin_required)):
    """Soft delete (archive) a prompt"""
    prompt = session.get(Prompt, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    prompt.status = "archived"
    prompt.updated_at = datetime.utcnow()
    session.add(prompt)
    session.commit()
    
    return {"message": "Prompt archived successfully"}

@router.post("/api/categories")
def create_category(
    session: SessionDep,
    admin=Depends(admin_required),
    name: str = Form(...),
    description: str = Form(""),
    parent_id: int = Form(None)
):
    """Create a new category"""
    from slugify import slugify
    
    category = Category(
        name=name,
        slug=slugify(name),
        description=description,
        parent_id=parent_id
    )
    session.add(category)
    session.commit()
    
    return {"message": "Category created successfully", "id": category.id}

@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request, session: SessionDep, admin=Depends(admin_required)):
    """Admin dashboard"""
    pending_submissions = session.exec(
        select(PromptSubmission).where(PromptSubmission.status == "pending")
    ).all()
    
    return templates.TemplateResponse(
        "admin/dashboard.html",
        {
            "request": request,
            "pending_count": len(pending_submissions)
        }
    )

@router.get("/submissions", response_class=HTMLResponse)
async def admin_submissions(request: Request, session: SessionDep, admin=Depends(admin_required)):
    """Admin submissions management"""
    submissions = session.exec(
        select(PromptSubmission).where(PromptSubmission.status == "pending")
    ).all()
    
    return templates.TemplateResponse(
        "admin/review_queue.html",
        {
            "request": request,
            "submissions": submissions
        }
    )