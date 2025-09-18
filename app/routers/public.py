from fastapi import APIRouter, Depends, Query, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from sqlmodel import select, or_, col
from app.database import SessionDep
from app.models import Prompt, Category, PromptSubmission, PromptDocument
from app.services.object_storage import object_storage_service
from typing import List, Dict, Any
import json
import requests

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
    categories = session.exec(select(Category).order_by(Category.sort_order)).all()
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
    categories = session.exec(select(Category).where(col(Category.parent_id).is_(None)).order_by(Category.sort_order)).all()
    return templates.TemplateResponse(
        "submit.html",
        {"request": request, "categories": categories}
    )

# File Serving Endpoints

@router.get("/documents/{file_path:path}")
async def serve_document(file_path: str, session: SessionDep):
    """Serve uploaded files securely
    
    This endpoint serves files from object storage. For private files, it checks
    if the document exists in the database and is associated with a published prompt.
    Public files are served directly.
    """
    try:
        # Check if file exists in object storage
        file_metadata = object_storage_service.get_file_metadata(file_path)
        if not file_metadata:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Check if this is a public file
        is_public = object_storage_service.is_file_public(file_path)
        
        if not is_public:
            # For private files, verify the document exists in database and is associated with published prompt
            document = session.exec(
                select(PromptDocument).where(PromptDocument.file_path == file_path)
            ).first()
            
            if not document:
                raise HTTPException(status_code=404, detail="Document not found")
            
            # Check if associated prompt is published
            prompt = session.get(Prompt, document.prompt_id)
            if not prompt or prompt.status != "published":
                raise HTTPException(status_code=404, detail="Document not accessible")
        
        # Generate presigned download URL and redirect to it
        download_url = object_storage_service.generate_presigned_download_url(
            file_path=file_path,
            expiry_minutes=60  # URL valid for 1 hour
        )
        
        # Redirect to the presigned URL for direct download
        return RedirectResponse(url=download_url, status_code=302)
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error serving file: {str(e)}"
        )

@router.get("/api/documents/{document_id}")
async def get_document_info(document_id: int, session: SessionDep):
    """Get document information by document ID"""
    document = session.get(PromptDocument, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Check if associated prompt is published
    prompt = session.get(Prompt, document.prompt_id)
    if not prompt or prompt.status != "published":
        raise HTTPException(status_code=404, detail="Document not accessible")
    
    # Return document information
    return {
        "id": document.id,
        "title": document.title,
        "document_type": document.document_type,
        "file_size": document.file_size,
        "mime_type": document.mime_type,
        "external_url": document.external_url,
        "download_url": f"/documents/{document.file_path}" if document.file_path else None,
        "created_at": document.created_at.isoformat()
    }