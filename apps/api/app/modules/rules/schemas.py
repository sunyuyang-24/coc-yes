"""Schemas for rulebook search."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RuleSearchRequest(BaseModel):
    keyword: str = Field(min_length=1, max_length=200)
    limit: int = 15


class RuleSearchResult(BaseModel):
    file: str
    page: int
    excerpt: str


class RuleSearchResponse(BaseModel):
    keyword: str
    total: int
    results: list[RuleSearchResult]