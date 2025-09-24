from fastapi import APIRouter, Depends, Request, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlmodel import select, or_, col
from app.database import SessionDep
from app.models import Prompt, Category, PromptDocument

router = APIRouter(prefix="/htmx", tags=["htmx"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/categories", response_class=HTMLResponse)
async def categories_partial(request: Request, session: SessionDep):
    """Render categories for sidebar"""
    categories = session.exec(select(Category).where(col(Category.parent_id).is_(None)).order_by(Category.sort_order)).all()
    
    return templates.TemplateResponse(
        "partials/categories.html",
        {"request": request, "categories": categories}
    )

@router.get("/prompts", response_class=HTMLResponse)
async def prompts_partial(
    request: Request, 
    session: SessionDep,
    query: str = Query(""),
    category: int = Query(None),
    page: int = Query(1),
    page_size: int = Query(20)
):
    """Render prompts list"""
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
    
    prompts = session.exec(stmt).all()
    
    # Get categories for display
    categories_data = session.exec(select(Category).order_by(Category.sort_order)).all()
    categories = {cat.id: cat.name for cat in categories_data}
    
    # Get prompt documents
    prompt_ids = [prompt.id for prompt in prompts]
    prompt_documents = {}
    if prompt_ids:
        documents = session.exec(
            select(PromptDocument).where(
                col(PromptDocument.prompt_id).in_(prompt_ids)
            ).order_by(PromptDocument.sort_order, PromptDocument.created_at)
        ).all()
        
        for doc in documents:
            if doc.prompt_id not in prompt_documents:
                prompt_documents[doc.prompt_id] = []
            prompt_documents[doc.prompt_id].append(doc)
    
    # Simple pagination
    total = len(prompts)
    start = (page - 1) * page_size
    items = prompts[start:start + page_size]
    
    return templates.TemplateResponse(
        "partials/prompts.html",
        {
            "request": request,
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "categories": categories,
            "prompt_documents": prompt_documents
        }
    )

@router.get("/prompts", response_class=HTMLResponse)
async def prompts_partial(
    request: Request, 
    session: SessionDep,
    query: str = "", 
    category: int | None = None,
    platform: str | None = None, 
    page: int = 1, 
    page_size: int = 20
):
    """Render prompts list"""
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
    
    # Get category names for display
    categories = {cat.id: cat.name for cat in session.exec(select(Category).order_by(Category.sort_order)).all()}
    
    # Get documents for each prompt
    prompt_documents = {}
    if prompts:
        prompt_ids = [p.id for p in prompts]
        documents_query = session.exec(
            select(PromptDocument)
            .where(PromptDocument.prompt_id.in_(prompt_ids))
            .order_by(PromptDocument.sort_order, PromptDocument.created_at)
        ).all()
        
        for doc in documents_query:
            if doc.prompt_id not in prompt_documents:
                prompt_documents[doc.prompt_id] = []
            prompt_documents[doc.prompt_id].append(doc)
    
    # Simple pagination
    total = len(prompts)
    start = (page - 1) * page_size
    items = prompts[start:start + page_size]
    
    return templates.TemplateResponse(
        "partials/prompts.html",
        {
            "request": request,
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "categories": categories,
            "prompt_documents": prompt_documents
        }
    )