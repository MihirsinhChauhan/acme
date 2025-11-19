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


