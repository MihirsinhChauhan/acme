"""Pydantic schemas for product resources."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


NonEmptyStr = Annotated[str, Field(min_length=1, max_length=255)]


class ProductBase(BaseModel):
    """Shared attributes for product payloads."""

    sku: NonEmptyStr = Field(description="Unique stock keeping unit identifier")
    name: NonEmptyStr = Field(description="Display name for the product")
    description: str | None = Field(default=None, description="Optional marketing copy")
    active: bool = Field(default=True, description="Indicates if the product is sellable")

    @field_validator("sku", "name", mode="before")
    @classmethod
    def strip_whitespace(cls, value: str) -> str:
        if isinstance(value, str):
            value = value.strip()
        return value


class ProductCreate(ProductBase):
    """Payload used when creating or importing a product."""

    pass


class ProductResponse(ProductBase):
    """Response model returned by API endpoints."""

    id: int = Field(description="Database identifier")
    created_at: datetime = Field(description="Timestamp when the product was created")
    updated_at: datetime = Field(description="Timestamp when the product was last updated")

    model_config = ConfigDict(from_attributes=True)


class CSVProductRow(ProductBase):
    """Represents a single CSV row used during validation."""

    @field_validator("sku", "name")
    @classmethod
    def ensure_not_empty(cls, value: str) -> str:
        if not value:
            msg = "Value cannot be empty for CSV row validation"
            raise ValueError(msg)
        return value


class ProductUpdate(BaseModel):
    """Payload used when updating a product (all fields optional)."""

    sku: NonEmptyStr | None = Field(default=None, description="Unique stock keeping unit identifier")
    name: NonEmptyStr | None = Field(default=None, description="Display name for the product")
    description: str | None = Field(default=None, description="Optional marketing copy")
    active: bool | None = Field(default=None, description="Indicates if the product is sellable")

    @field_validator("sku", "name", mode="before")
    @classmethod
    def strip_whitespace(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            value = value.strip()
        return value


class ProductFilter(BaseModel):
    """Query parameters for filtering products."""

    sku: str | None = Field(default=None, description="Filter by SKU (partial match, case-insensitive)")
    name: str | None = Field(default=None, description="Filter by name (partial match, case-insensitive)")
    description: str | None = Field(default=None, description="Filter by description (partial match, case-insensitive)")
    active: bool | None = Field(default=None, description="Filter by active status")


class ProductListResponse(BaseModel):
    """Paginated response wrapper for product lists."""

    items: list[ProductResponse] = Field(description="List of products in this page")
    total: int = Field(description="Total number of products matching the filters")
    page: int = Field(description="Current page number (1-indexed)")
    page_size: int = Field(description="Number of items per page")

    model_config = ConfigDict(from_attributes=True)

