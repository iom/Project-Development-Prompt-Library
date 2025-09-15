from fastapi import APIRouter, Depends, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlmodel import select, or_, col
from app.database import SessionDep
from app.models import Prompt, Category

router = APIRouter(prefix="/htmx", tags=["htmx"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/categories", response_class=HTMLResponse)
async def categories_partial(request: Request, session: SessionDep):
    """Render categories for sidebar"""
    categories = session.exec(select(Category).where(col(Category.parent_id).is_(None))).all()
    
    html = """
    <div class="space-y-2">
        <button onclick="selectCategory('')" class="block w-full text-left px-3 py-2 rounded-md hover:bg-gray-100 text-sm">
            All Categories
        </button>
    """
    for category in categories:
        html += f"""
        <button onclick="selectCategory({category.id})" class="block w-full text-left px-3 py-2 rounded-md hover:bg-gray-100 text-sm">
            {category.name}
        </button>
        """
    
    html += "</div>"
    return HTMLResponse(content=html)

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
    categories = {cat.id: cat.name for cat in session.exec(select(Category)).all()}
    
    # Simple pagination
    total = len(prompts)
    start = (page - 1) * page_size
    items = prompts[start:start + page_size]
    
    html = f"""
    <div class="space-y-4">
        <div class="text-sm text-gray-600 mb-4">
            Found {total} prompts
        </div>
    """
    
    for prompt in items:
        category_name = categories.get(prompt.category_id, 'Unknown')
        excerpt = prompt.body[:200] + "..." if len(prompt.body) > 200 else prompt.body
        
        html += f"""
        <div class="bg-white rounded-lg shadow p-6 hover:shadow-md transition-shadow">
            <div class="flex justify-between items-start mb-3">
                <div class="flex-1">
                    <h3 class="text-lg font-semibold text-gray-900 mb-1">
                        <a href="/prompt/{prompt.id}" class="hover:text-blue-600">{prompt.title}</a>
                    </h3>
                    <div class="flex items-center space-x-2 text-sm text-gray-600">
                        <span class="inline-flex items-center">
                            <i class="fas fa-folder mr-1"></i>
                            {category_name}
                        </span>
                        {f'<span class="inline-flex items-center"><i class="fas fa-robot mr-1"></i>{prompt.ai_platform}</span>' if prompt.ai_platform else ''}
                    </div>
                </div>
                <button onclick="copyPrompt('{prompt.id}')" 
                        class="bg-blue-600 text-white px-3 py-1 rounded text-sm hover:bg-blue-700">
                    Copy
                </button>
            </div>
            <p class="text-gray-700 text-sm leading-relaxed">{excerpt}</p>
        </div>
        """
    
    html += "</div>"
    
    if total > page_size:
        total_pages = (total + page_size - 1) // page_size
        html += f"""
        <div class="flex justify-center mt-6 space-x-2">
        """
        for p in range(1, min(total_pages + 1, 6)):  # Show up to 5 pages
            active_class = "bg-blue-600 text-white" if p == page else "bg-white text-gray-700 hover:bg-gray-50"
            html += f"""
            <button onclick="loadPage({p})" class="{active_class} px-3 py-2 rounded-md border text-sm">
                {p}
            </button>
            """
        html += "</div>"
    
    return HTMLResponse(content=html)