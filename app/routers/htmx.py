from fastapi import APIRouter, Depends, Request, Query
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from sqlmodel import select, or_, col
from sqlalchemy import func 
from app.database import SessionDep
from app.models import Prompt, Category, PromptDocument

router = APIRouter(prefix="/htmx", tags=["htmx"])
templates = Jinja2Templates(directory="app/templates")

@router.get("/categories", response_class=HTMLResponse)
async def categories_partial(
    request: Request,
    session: SessionDep,
    selected: int | None = Query(None),
):
    categories = session.exec(select(Category).order_by(Category.sort_order)).all()

    # Maps
    parent_map = {c.id: c.parent_id for c in categories}
    children_map = {}
    for c in categories:
        children_map.setdefault(c.parent_id, []).append(c.id)

    # Leaf counts (published only) → roll up as before
    rows = session.exec(
        select(Prompt.category_id, func.count(Prompt.id))
        .where(Prompt.status == "published")
        .group_by(Prompt.category_id)
    ).all()
    leaf_counts = {cat_id: cnt for (cat_id, cnt) in rows}
    totals = {c.id: leaf_counts.get(c.id, 0) for c in categories}

    # Depth + roll-up
    depth = {}
    def get_depth(cid):
        if cid in depth:
            return depth[cid]
        p = parent_map[cid]
        depth[cid] = 0 if p is None else get_depth(p) + 1
        return depth[cid]
    for c in categories:
        get_depth(c.id)
    for cid, _d in sorted(depth.items(), key=lambda kv: -kv[1]):
        p = parent_map[cid]
        if p is not None:
            totals[p] = totals.get(p, 0) + totals.get(cid, 0)

    # Ancestors of selected for auto-open
    open_ids = set()
    cur = selected
    while cur is not None and cur in parent_map:
        open_ids.add(parent_map[cur])
        cur = parent_map[cur]

    return templates.TemplateResponse(
        "partials/categories.html",
        {
            "request": request,
            "categories": categories,
            "counts": totals,
            "children_map": children_map,
            "selected": selected,  
            "open_ids": open_ids, 
        }
    )


@router.get("/prompts", response_class=HTMLResponse)
async def prompts_partial(
    request: Request, 
    session: SessionDep,
    query: str = Query(""),
    category: int | None = Query(None),
    page: int = Query(1),
    page_size: int = Query(20)
):
    """Render prompts list; when a parent is selected, include all prompts in its subtree."""
    # Base
    stmt = select(Prompt).where(Prompt.status == "published")

    # Search
    if query:
        like = f"%{query}%"
        from sqlmodel import or_
        stmt = stmt.where(
            or_(
                col(Prompt.title).ilike(like),
                col(Prompt.body).ilike(like),
                col(Prompt.instructions).ilike(like),
            )
        )

    # Category subtree filter (only category_id, no subcategory_id)
    if category:
        all_cats = session.exec(select(Category)).all()

        # Build children map
        from collections import defaultdict
        children_map = defaultdict(list)
        for c in all_cats:
            children_map[c.parent_id].append(c.id)

        # Collect subtree ids
        ids = set()
        stack = [category]
        while stack:
            cid = stack.pop()
            if cid in ids:
                continue
            ids.add(cid)
            stack.extend(children_map.get(cid, []))

        stmt = stmt.where(col(Prompt.category_id).in_(ids))

    prompts = session.exec(stmt).all()

    # Categories map for template display
    categories_data = session.exec(select(Category).order_by(Category.sort_order)).all()
    categories = {cat.id: cat.name for cat in categories_data}

    # Documents per prompt (batched)
    prompt_documents = {}
    if prompts:
        pids = [p.id for p in prompts]
        docs = session.exec(
            select(PromptDocument)
            .where(col(PromptDocument.prompt_id).in_(pids))
            .order_by(PromptDocument.sort_order, PromptDocument.created_at)
        ).all()
        for d in docs:
            prompt_documents.setdefault(d.prompt_id, []).append(d)

    # Pagination
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
            "prompt_documents": prompt_documents,
        }
    )
