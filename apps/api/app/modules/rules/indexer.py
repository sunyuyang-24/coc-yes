"""Build a page-level text index from the COC 7e rulebook PDF."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import fitz


# ---------------------------------------------------------------------------
# data types
# ---------------------------------------------------------------------------

@dataclass
class RulePage:
    page_number: int          # 1-based page number
    text: str                 # full extracted text


@dataclass
class RuleIndex:
    source_path: str          # absolute PDF path
    total_pages: int
    pages: list[RulePage] = field(default_factory=list)


# ---------------------------------------------------------------------------
# extraction helpers
# ---------------------------------------------------------------------------

def _clean_text(raw: str) -> str:
    """Collapse whitespace and strip leading/trailing noise."""
    text = re.sub(r"\s+", " ", raw)
    return text.strip()


def build_index(pdf_path: Path) -> RuleIndex:
    """Extract all pages from *pdf_path* and return a RuleIndex."""
    doc = fitz.open(str(pdf_path))
    index = RuleIndex(source_path=str(pdf_path.resolve()), total_pages=doc.page_count)

    for page_num in range(doc.page_count):
        raw = doc[page_num].get_text()
        cleaned = _clean_text(raw)
        if cleaned:
            index.pages.append(RulePage(page_number=page_num + 1, text=cleaned))

    doc.close()
    return index


# ---------------------------------------------------------------------------
# search
# ---------------------------------------------------------------------------

def search_index(index: RuleIndex, keyword: str, limit: int = 15) -> list[dict[str, Any]]:
    """Keyword search across indexed pages. Returns list of result dicts."""
    results: list[dict[str, Any]] = []
    kw_lower = keyword.lower()

    for page in index.pages:
        pos = page.text.lower().find(kw_lower)
        if pos == -1:
            continue

        # extract a window around the match
        start = max(0, pos - 60)
        end = min(len(page.text), pos + len(keyword) + 120)
        excerpt = page.text[start:end]

        # try to find a natural sentence boundary for cleaner display
        if start > 0:
            # extend backward to nearest period or sentence start
            prev_period = page.text.rfind("。", 0, start)
            prev_dot = page.text.rfind(". ", 0, start)
            cut = max(prev_period, prev_dot)
            if cut != -1 and (start - cut) < 80:
                excerpt = page.text[cut + 1:end].strip()

        # add ellipsis markers
        if start > 0:
            excerpt = "..." + excerpt
        if end < len(page.text):
            excerpt = excerpt + "..."

        results.append({
            "file": "COC7th核心规则书原文.pdf",
            "page": page.page_number,
            "excerpt": excerpt.strip(),
        })

        if len(results) >= limit:
            break

    return results


# ---------------------------------------------------------------------------
# persistence
# ---------------------------------------------------------------------------

def save_index(index: RuleIndex, target: Path) -> None:
    """Serialize index to JSON."""
    data = {
        "source_path": index.source_path,
        "total_pages": index.total_pages,
        "pages": [{"page_number": p.page_number, "text": p.text} for p in index.pages],
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def load_index(path: Path) -> RuleIndex:
    """Deserialize index from JSON."""
    data = json.loads(path.read_text(encoding="utf-8"))
    idx = RuleIndex(source_path=data["source_path"], total_pages=data["total_pages"])
    for p in data["pages"]:
        idx.pages.append(RulePage(page_number=p["page_number"], text=p["text"]))
    return idx