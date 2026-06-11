"""API routes for rulebook search."""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.core.config import settings, REPO_ROOT
from app.modules.rules.indexer import build_index, load_index, search_index
from app.modules.rules.schemas import RuleSearchRequest, RuleSearchResponse, RuleSearchResult

logger = logging.getLogger(__name__)

router = APIRouter()

# Default PDF path
_DEFAULT_PDF = REPO_ROOT / "COC7th核心规则书原文.pdf"
_INDEX_CACHE: Path = settings.data_dir / "rules-index.json"


def _ensure_index():
    """Build index on first call if it doesn't exist."""
    if _INDEX_CACHE.exists():
        return load_index(_INDEX_CACHE)
    if not _DEFAULT_PDF.exists():
        raise HTTPException(status_code=503, detail="规则书PDF文件未找到，请放入 COC7th核心规则书原文.pdf")
    logger.info("Building rulebook index (first run)...")
    idx = build_index(_DEFAULT_PDF)
    from app.modules.rules.indexer import save_index
    save_index(idx, _INDEX_CACHE)
    logger.info("Index built: %d pages with text", len(idx.pages))
    return idx


@router.get("/rules/index-status")
def index_status():
    """Return index status info."""
    if _INDEX_CACHE.exists():
        from app.modules.rules.indexer import load_index
        idx = load_index(_INDEX_CACHE)
        return {
            "ready": True,
            "source_file": idx.source_path,
            "total_pages": idx.total_pages,
            "indexed_pages": len(idx.pages),
        }
    return {
        "ready": False,
        "pdf_exists": _DEFAULT_PDF.exists(),
    }


@router.post("/rules/search", response_model=RuleSearchResponse)
def search_rules(req: RuleSearchRequest):
    """Full-text search across the rulebook index."""
    if not req.keyword.strip():
        return RuleSearchResponse(keyword=req.keyword, total=0, results=[])

    idx = _ensure_index()
    hits = search_index(idx, req.keyword.strip(), limit=req.limit)
    return RuleSearchResponse(
        keyword=req.keyword,
        total=len(hits),
        results=[RuleSearchResult(**h) for h in hits],
    )


@router.post("/rules/rebuild-index")
def rebuild_index():
    """Force rebuild the index (e.g. after PDF update)."""
    if not _DEFAULT_PDF.exists():
        raise HTTPException(status_code=503, detail="规则书PDF文件未找到")
    _INDEX_CACHE.unlink(missing_ok=True)
    idx = build_index(_DEFAULT_PDF)
    from app.modules.rules.indexer import save_index
    save_index(idx, _INDEX_CACHE)
    logger.info("Index rebuilt: %d text pages", len(idx.pages))
    return {"ready": True, "total_pages": idx.total_pages, "indexed_pages": len(idx.pages)}