from fastapi import APIRouter, Depends, HTTPException, Request, Form, Response, File, UploadFile
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlmodel import select
from sqlalchemy import func
from app.database import SessionDep
from app.models import PromptSubmission, Prompt, Category, AuditLog, PromptDocument, User, UserRole
from app.services.object_storage import object_storage_service
from datetime import datetime
from typing import Optional, List
import json

router = APIRouter(prefix="/secure-admin-2024", tags=["admin"])
templates = Jinja2Templates(directory="app/templates")

# Admin authentication for hidden path
def admin_required(request: Request):
    """Admin access control for hidden admin site"""
    import os
    
    # Check session cookie first (for HTML requests)
    admin_session = request.cookies.get("admin_session")
    if admin_session == os.getenv("ADMIN_KEY"):
        return {"admin": True}
    
    # Fallback to header check (for API requests)
    required_key = os.getenv("ADMIN_KEY")
    if not required_key:
        raise HTTPException(status_code=500, detail="Admin key not configured")
    
    admin_key = request.headers.get("X-Admin-Key")
    if admin_key == required_key:
        return {"admin": True}
        
    raise HTTPException(status_code=403, detail="Admin access required")

@router.get("/api/categories")
def admin_categories(session: SessionDep, admin=Depends(admin_required)):
    """Get all categories for admin"""
    categories = session.exec(select(Category).order_by(Category.sort_order)).all()
    return categories

@router.get("/api/prompts")  
def admin_prompts(session: SessionDep, admin=Depends(admin_required)):
    """Get all prompts for admin"""
    prompts = session.exec(select(Prompt)).all()
    return prompts

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
    category_action: str = Form(None),  # 'existing' or 'new'
    category_id: int = Form(None),  # For mapping to existing category
    new_category_name: str = Form(None),  # For creating new category
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
        final_category_id = submission.category_id
        
        # Handle category resolution for suggested categories
        if submission.suggested_category_name and category_action:
            if category_action == "existing":
                if not category_id:
                    raise HTTPException(status_code=400, detail="Category ID required for existing category mapping")
                
                # Validate that the category exists
                existing_category = session.get(Category, category_id)
                if not existing_category:
                    raise HTTPException(status_code=404, detail="Selected category not found")
                final_category_id = category_id
                
            elif category_action == "new":
                if not new_category_name or not new_category_name.strip():
                    raise HTTPException(status_code=400, detail="Category name required for new category creation")
                
                # Create new category with uniqueness handling
                from slugify import slugify
                category_name = new_category_name.strip()
                base_slug = slugify(category_name)
                
                try:
                    # Check for existing category with same name or slug
                    existing = session.exec(
                        select(Category).where(
                            (Category.name == category_name) | (Category.slug == base_slug)
                        )
                    ).first()
                    
                    if existing:
                        # If exact match exists, reuse it
                        final_category_id = existing.id
                    else:
                        # Create new category with proper sort_order
                        # Get next sort_order for new category (appears at end)
                        max_sort_order = session.exec(
                            select(func.max(Category.sort_order))
                        ).first()
                        next_sort_order = (max_sort_order or 0) + 1
                        
                        new_category = Category(
                            name=category_name,
                            slug=base_slug,
                            description=f"Category created from user suggestion: {submission.suggested_category_name}",
                            sort_order=next_sort_order
                        )
                        session.add(new_category)
                        session.commit()
                        session.refresh(new_category)
                        final_category_id = new_category.id
                        
                except Exception as e:
                    # Handle any database integrity errors
                    session.rollback()
                    raise HTTPException(status_code=409, detail=f"Category creation failed: {str(e)}")
        
        # Ensure we have a valid category_id
        if not final_category_id:
            raise HTTPException(status_code=400, detail="Valid category is required for approval")
        
        prompt = Prompt(
            title=submission.title,
            body=submission.body,
            category_id=final_category_id,
            subcategory_id=submission.subcategory_id,
            instructions=submission.instructions,
            tags=submission.tags,
            status="published",
            created_by=submission.submitted_by
        )
        # Set platforms from submission
        prompt.set_platforms(submission.get_platforms())
        session.add(prompt)
        session.commit()
        session.refresh(prompt)
        
        submission.approved_prompt_id = prompt.id
    
    session.add(submission)
    session.commit()
    
    return {"message": f"Submission {status} successfully"}


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
    platform_choice: list = Form([]),
    ai_platforms: str = Form(None),
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
    if ai_platforms is not None:
        # Parse comma-separated platforms or JSON
        try:
            if ai_platforms.startswith('['):
                platforms = json.loads(ai_platforms)
            else:
                platforms = [p.strip() for p in ai_platforms.split(',') if p.strip()]
            prompt.set_platforms(platforms)
        except (json.JSONDecodeError, AttributeError):
            # Fallback to single platform
            if ai_platforms:
                prompt.set_platforms([ai_platforms])
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
    request: Request,
    session: SessionDep,
    admin=Depends(admin_required),
    name: str = Form(...),
    description: str = Form(""),
    parent_id: str = Form("")  # Accept as string
):
    """Create a new category"""
    from slugify import slugify

    # Convert empty string to None, otherwise to int
    if parent_id == "" or parent_id is None:
        parent_id_int = None
    else:
        parent_id_int = int(parent_id)

    # Get the highest sort_order and add 1 for new category (appears at end)
    max_sort_order = session.exec(
        select(func.max(Category.sort_order))
    ).first()
    next_sort_order = (max_sort_order or 0) + 1

    category = Category(
        name=name,
        slug=slugify(name),
        description=description,
        parent_id=parent_id_int,
        sort_order=next_sort_order
    )
    session.add(category)
    session.commit()

    # Redirect back to categories page for HTML form submission
    if "text/html" in request.headers.get("accept", ""):
        return RedirectResponse(url="/secure-admin-2024/categories", status_code=303)

    return {"message": "Category created successfully", "id": category.id}

@router.get("/")
def admin_root(request: Request):
    """Admin root - redirect to appropriate page"""
    import os
    
    # Check if user is already authenticated
    admin_session = request.cookies.get("admin_session")
    required_key = os.getenv("ADMIN_KEY")
    
    if admin_session == required_key:
        return RedirectResponse(url="/secure-admin-2024/dashboard", status_code=303)
    else:
        return RedirectResponse(url="/secure-admin-2024/login", status_code=303)

@router.get("/login", response_class=HTMLResponse)  
def admin_login_page(request: Request):
    """Admin login page"""
    return templates.TemplateResponse("admin/login.html", {"request": request})

@router.post("/login")
def admin_login_submit(request: Request, admin_key: str = Form(...)):
    """Process admin login"""
    import os
    required_key = os.getenv("ADMIN_KEY")
    if not required_key:
        raise HTTPException(status_code=500, detail="Admin key not configured")
    
    if admin_key == required_key:
        response = RedirectResponse(url="/secure-admin-2024/dashboard", status_code=303)
        response.set_cookie(
            key="admin_session", 
            value=admin_key, 
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            max_age=3600  # 1 hour
        )
        return response
    else:
        # Return to login with error
        return templates.TemplateResponse(
            "admin/login.html", 
            {"request": request, "error": "Invalid admin key"}
        )

@router.post("/logout")
def admin_logout():
    """Admin logout"""
    response = RedirectResponse(url="/secure-admin-2024/login", status_code=303)
    response.delete_cookie("admin_session")
    return response

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

@router.get("/prompts", response_class=HTMLResponse)
async def admin_prompts_page(request: Request, session: SessionDep, admin=Depends(admin_required)):
    """Admin prompts management page"""
    prompts = session.exec(select(Prompt)).all()
    categories = session.exec(select(Category)).all()
    
    # Create category lookup
    category_dict = {cat.id: cat.name for cat in categories}
    
    return templates.TemplateResponse(
        "admin/prompts.html",
        {
            "request": request,
            "prompts": prompts,
            "categories": category_dict
        }
    )

@router.get("/prompts/new", response_class=HTMLResponse)
async def admin_new_prompt_page(request: Request, session: SessionDep, admin=Depends(admin_required)):
    """New prompt form"""
    categories = session.exec(select(Category)).all()
    
    return templates.TemplateResponse(
        "admin/prompt_form.html",
        {
            "request": request,
            "categories": categories,
            "prompt": None
        }
    )

@router.post("/prompts/new")
async def admin_create_prompt(
    request: Request,
    session: SessionDep,
    admin=Depends(admin_required),
    title: str = Form(...),
    body: str = Form(...),
    category_id: int = Form(...),
    platform_choice: list = Form([]),
    ai_platforms: str = Form(None),
    instructions: str = Form(""),
    tags: str = Form(""),
    status: str = Form("published")
):
    """Create new prompt"""
    prompt = Prompt(
        title=title,
        body=body,
        category_id=category_id,
        instructions=instructions if instructions else None,
        tags=tags if tags else None,
        status=status,
        created_by=None  # Admin created
    )
    
    # Set platforms
    if ai_platforms:
        try:
            if ai_platforms.startswith('['):
                platforms = json.loads(ai_platforms)
            else:
                platforms = [p.strip() for p in ai_platforms.split(',') if p.strip()]
            prompt.set_platforms(platforms)
        except (json.JSONDecodeError, AttributeError):
            if ai_platforms:
                prompt.set_platforms([ai_platforms])
    else:
        prompt.set_platforms([])
    
    session.add(prompt)
    session.commit()
    
    return RedirectResponse(url="/secure-admin-2024/prompts", status_code=303)

@router.get("/prompts/{prompt_id}/edit", response_class=HTMLResponse)
async def admin_edit_prompt_page(prompt_id: int, request: Request, session: SessionDep, admin=Depends(admin_required)):
    """Edit prompt form"""
    prompt = session.get(Prompt, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    categories = session.exec(select(Category)).all()
    
    # Get existing documents for this prompt
    documents = session.exec(
        select(PromptDocument)
        .where(PromptDocument.prompt_id == prompt_id)
        .order_by(PromptDocument.sort_order, PromptDocument.created_at)
    ).all()
    
    return templates.TemplateResponse(
        "admin/prompt_form.html",
        {
            "request": request,
            "prompt": prompt,
            "categories": categories,
            "documents": documents
        }
    )

@router.post("/prompts/{prompt_id}/edit")
async def admin_update_prompt_form(
    prompt_id: int,
    request: Request,
    session: SessionDep,
    admin=Depends(admin_required),
    title: str = Form(...),
    body: str = Form(...),
    category_id: int = Form(...),
    platform_choice: list = Form([]),
    ai_platforms: str = Form(None),
    instructions: str = Form(""),
    tags: str = Form(""),
    status: str = Form("published")
):
    """Update prompt via form"""
    
    prompt = session.get(Prompt, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    prompt.title = title
    prompt.body = body
    prompt.category_id = category_id
    prompt.instructions = instructions if instructions else None
    prompt.tags = tags if tags else None
    prompt.status = status
    prompt.updated_at = datetime.utcnow()
    
    # Set platforms - use either checkbox values or JSON field
    if platform_choice:  # Direct checkbox values received
        prompt.set_platforms(platform_choice)
    elif ai_platforms is not None:  # Fallback to JSON field
        if ai_platforms:
            try:
                if ai_platforms.startswith('['):
                    platforms = json.loads(ai_platforms)
                else:
                    platforms = [p.strip() for p in ai_platforms.split(',') if p.strip()]
                prompt.set_platforms(platforms)
            except (json.JSONDecodeError, AttributeError):
                if ai_platforms:
                    prompt.set_platforms([ai_platforms])
        else:
            prompt.set_platforms([])
    
    session.add(prompt)
    session.commit()
    
    return RedirectResponse(url="/secure-admin-2024/prompts", status_code=303)

@router.get("/categories", response_class=HTMLResponse)
async def admin_categories_page(request: Request, session: SessionDep, admin=Depends(admin_required)):
    """Admin categories management page"""
    categories = session.exec(select(Category).order_by(Category.sort_order)).all()
    
    # Count prompts per category
    category_counts = {}
    for category in categories:
        count = len(session.exec(
            select(Prompt).where(Prompt.category_id == category.id)
        ).all())
        category_counts[category.id] = count
    
    return templates.TemplateResponse(
        "admin/categories.html",
        {
            "request": request,
            "categories": categories,
            "category_counts": category_counts
        }
    )

@router.patch("/api/categories/{category_id}")
async def update_category(
    category_id: int,
    session: SessionDep,
    admin=Depends(admin_required),
    name: str = Form(...),
    description: str = Form(""),
    parent_id: str = Form("")
):
    """Update a category"""
    from slugify import slugify

    # Convert empty string to None, otherwise to int
    if parent_id == "" or parent_id is None:
        parent_id_int = None
    else:
        try:
            parent_id_int = int(parent_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid parent_id")

    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    category.name = name
    category.slug = slugify(name)
    category.description = description
    category.updated_at = datetime.utcnow()
    category.parent_id = parent_id_int

    session.add(category)
    session.commit()

    return {"message": "Category updated successfully"}

@router.patch("/api/categories/{category_id}/move-up")
async def move_category_up(
    category_id: int,
    session: SessionDep,
    admin=Depends(admin_required)
):
    """Move category up in sort order"""
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Find the category with the next lower sort_order
    prev_category = session.exec(
        select(Category)
        .where(Category.sort_order < category.sort_order)
        .order_by(Category.sort_order.desc())
    ).first()
    
    if not prev_category:
        return {"message": "Category is already at the top"}
    
    # Swap sort orders
    category.sort_order, prev_category.sort_order = prev_category.sort_order, category.sort_order
    category.updated_at = datetime.utcnow()
    prev_category.updated_at = datetime.utcnow()
    
    session.add(category)
    session.add(prev_category)
    session.commit()
    
    return {"message": "Category moved up successfully"}

@router.patch("/api/categories/{category_id}/move-down")
async def move_category_down(
    category_id: int,
    session: SessionDep,
    admin=Depends(admin_required)
):
    """Move category down in sort order"""
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Find the category with the next higher sort_order
    next_category = session.exec(
        select(Category)
        .where(Category.sort_order > category.sort_order)
        .order_by(Category.sort_order.asc())
    ).first()
    
    if not next_category:
        return {"message": "Category is already at the bottom"}
    
    # Swap sort orders
    category.sort_order, next_category.sort_order = next_category.sort_order, category.sort_order
    category.updated_at = datetime.utcnow()
    next_category.updated_at = datetime.utcnow()
    
    session.add(category)
    session.add(next_category)
    session.commit()
    
    return {"message": "Category moved down successfully"}

# Document/File Upload Endpoints

@router.post("/api/documents/upload")
async def get_presigned_upload_url(
    session: SessionDep,
    admin=Depends(admin_required),
    filename: str = Form(...),
    content_type: str = Form(...),
    size: int = Form(...),
    is_public: bool = Form(False),
    prompt_id: Optional[int] = Form(None)
):
    """Get presigned upload URL for document upload to object storage"""
    try:
        # Validate file size (max 50MB)
        MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB in bytes
        if size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File size too large. Maximum allowed: {MAX_FILE_SIZE // (1024*1024)}MB"
            )
        
        # Validate file type
        is_valid, detected_mime = object_storage_service.validate_file_type(filename)
        if not is_valid:
            raise HTTPException(
                status_code=400, 
                detail=f"File type not allowed. Detected: {detected_mime}"
            )
        
        # Use detected MIME type if different from provided
        final_content_type = detected_mime if detected_mime != "unknown" else content_type
        
        # Generate presigned upload URL
        upload_data = object_storage_service.generate_presigned_upload_url(
            filename=filename,
            content_type=final_content_type,
            is_public=is_public,
            expiry_minutes=15
        )
        
        # Return upload data for frontend to use
        return {
            "upload_url": upload_data["upload_url"],
            "file_path": upload_data["file_path"],
            "unique_filename": upload_data["unique_filename"],
            "original_filename": upload_data["original_filename"],
            "content_type": upload_data["content_type"],
            "is_public": upload_data["is_public"],
            "expires_at": upload_data["expires_at"]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate upload URL: {str(e)}")

@router.post("/api/documents")
async def save_document_metadata(
    session: SessionDep,
    admin=Depends(admin_required),
    prompt_id: int = Form(...),
    title: str = Form(...),
    document_type: str = Form(...),  # 'file' or 'link'
    file_path: Optional[str] = Form(None),  # For uploaded files
    external_url: Optional[str] = Form(None),  # For external links
    file_size: Optional[int] = Form(None),
    mime_type: Optional[str] = Form(None),
    sort_order: int = Form(0)
):
    """Save document metadata after successful upload or add external link"""
    
    # Validate prompt exists
    prompt = session.get(Prompt, prompt_id)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    
    # Validate document type and required fields
    if document_type not in ["file", "link"]:
        raise HTTPException(status_code=400, detail="Document type must be 'file' or 'link'")
    
    if document_type == "file" and not file_path:
        raise HTTPException(status_code=400, detail="file_path is required for file documents")
    
    if document_type == "link" and not external_url:
        raise HTTPException(status_code=400, detail="external_url is required for link documents")
    
    # For uploaded files, verify file exists in object storage
    if document_type == "file" and file_path:
        try:
            file_metadata = object_storage_service.get_file_metadata(file_path)
            if not file_metadata:
                raise HTTPException(status_code=404, detail="Uploaded file not found in storage")
            
            # Use actual file metadata if not provided
            if not file_size:
                file_size = file_metadata.get("size")
            if not mime_type:
                mime_type = file_metadata.get("content_type")
                
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to verify uploaded file: {str(e)}")
    
    # Create document record
    document = PromptDocument(
        prompt_id=prompt_id,
        title=title,
        document_type=document_type,
        file_path=file_path,
        external_url=external_url,
        file_size=file_size,
        mime_type=mime_type,
        sort_order=sort_order
    )
    
    session.add(document)
    session.commit()
    session.refresh(document)
    
    return {
        "message": "Document saved successfully",
        "document_id": document.id,
        "document": {
            "id": document.id,
            "title": document.title,
            "document_type": document.document_type,
            "file_path": document.file_path,
            "external_url": document.external_url,
            "file_size": document.file_size,
            "mime_type": document.mime_type,
            "sort_order": document.sort_order,
            "created_at": document.created_at.isoformat()
        }
    }

@router.get("/api/documents")
async def list_documents(
    session: SessionDep,
    admin=Depends(admin_required),
    prompt_id: Optional[int] = None
):
    """List documents, optionally filtered by prompt_id"""
    query = select(PromptDocument).order_by(PromptDocument.sort_order, PromptDocument.created_at)
    
    if prompt_id:
        query = query.where(PromptDocument.prompt_id == prompt_id)
    
    documents = session.exec(query).all()
    
    return {
        "documents": [
            {
                "id": doc.id,
                "prompt_id": doc.prompt_id,
                "title": doc.title,
                "document_type": doc.document_type,
                "file_path": doc.file_path,
                "external_url": doc.external_url,
                "file_size": doc.file_size,
                "mime_type": doc.mime_type,
                "sort_order": doc.sort_order,
                "created_at": doc.created_at.isoformat(),
                "updated_at": doc.updated_at.isoformat()
            }
            for doc in documents
        ]
    }

@router.delete("/api/documents/{doc_id}")
async def delete_document(
    doc_id: int,
    session: SessionDep,
    admin=Depends(admin_required)
):
    """Delete document and associated file from object storage if applicable"""
    
    document = session.get(PromptDocument, doc_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # If it's a file document, delete from object storage
    if document.document_type == "file" and document.file_path:
        try:
            deleted = object_storage_service.delete_file(document.file_path)
            if not deleted:
                # File was not found in storage, but we'll continue with database deletion
                pass
        except Exception as e:
            # Log error but continue with database deletion
            print(f"Warning: Failed to delete file from storage: {str(e)}")
    
    # Delete from database
    session.delete(document)
    session.commit()
    
    return {
        "message": "Document deleted successfully",
        "document_id": doc_id
    }

# --- User Management Endpoints ---

@router.get("/users", response_class=HTMLResponse)
def admin_users_page(request: Request, session: SessionDep, admin=Depends(admin_required)):
    users = session.exec(select(User)).all()
    roles = session.exec(select(UserRole)).all()
    return templates.TemplateResponse(
        "admin/users.html",
        {"request": request, "users": users, "roles": roles}
    )

@router.post("/api/users")
def create_user(
    request: Request,
    session: SessionDep,
    admin=Depends(admin_required),
    username: str = Form(...),
    email: str = Form(...),
    role_id: int = Form(...),
):
    user = User(username=username, email=email, role_id=role_id)
    session.add(user)
    session.commit()
    return {"message": "User created successfully", "id": user.id}

@router.patch("/api/users/{user_id}")
def update_user(
    user_id: int,
    session: SessionDep,
    admin=Depends(admin_required),
    username: str = Form(...),
    email: str = Form(...),
    role_id: int = Form(...),
):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.username = username
    user.email = email
    user.role_id = role_id
    session.add(user)
    session.commit()
    return {"message": "User updated successfully"}

@router.delete("/api/users/{user_id}")
def delete_user(user_id: int, session: SessionDep, admin=Depends(admin_required)):
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    session.delete(user)
    session.commit()
    return {"message": "User deleted successfully"}