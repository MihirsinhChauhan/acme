"""Product repository for batch operations and database access."""
from __future__ import annotations

from typing import Sequence

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.product import Product
from app.schemas.product import ProductCreate


class ProductRepository:
    """Handles database operations for Product entities."""

    def __init__(self, session: Session) -> None:
        """Initialize repository with a SQLAlchemy session.
        
        Args:
            session: Active database session for executing queries
        """
        self._session = session

    def batch_upsert(self, products: Sequence[ProductCreate]) -> int:
        """Bulk insert or update products based on case-insensitive SKU matching.
        
        Uses PostgreSQL's INSERT ... ON CONFLICT to handle duplicate SKUs efficiently.
        The unique constraint is on LOWER(sku), so matching is case-insensitive.
        
        Args:
            products: Sequence of ProductCreate schemas to insert/update
            
        Returns:
            Number of rows affected (inserted or updated)
            
        Raises:
            SQLAlchemyError: If database operation fails
        """
        if not products:
            return 0

        # Prepare product data as dictionaries
        product_dicts = [
            {
                "sku": p.sku,
                "name": p.name,
                "description": p.description,
                "active": p.active,
            }
            for p in products
        ]

        # Build PostgreSQL INSERT ... ON CONFLICT statement
        stmt = insert(Product).values(product_dicts)
        
        # Update all fields except id, created_at when SKU conflict occurs
        # The unique index is on LOWER(sku), so we reference the expression
        update_dict = {
            "name": stmt.excluded.name,
            "description": stmt.excluded.description,
            "active": stmt.excluded.active,
        }
        
        stmt = stmt.on_conflict_do_update(
            index_elements=[func.lower(Product.sku)],  # Must match the unique index expression
            set_=update_dict,
        )

        result = self._session.execute(stmt)
        self._session.commit()
        
        return result.rowcount

    def get_by_sku(self, sku: str) -> Product | None:
        """Fetch a product by SKU (case-insensitive).
        
        Args:
            sku: Stock keeping unit identifier
            
        Returns:
            Product instance if found, None otherwise
        """
        # Use LOWER() to ensure case-insensitive lookup
        return (
            self._session.query(Product)
            .filter(func.lower(Product.sku) == func.lower(sku))
            .first()
        )

    def get_by_id(self, product_id: int) -> Product | None:
        """Fetch a product by its database ID.
        
        Args:
            product_id: Database identifier
            
        Returns:
            Product instance if found, None otherwise
        """
        return self._session.get(Product, product_id)

    def get_all(self, limit: int = 100, offset: int = 0) -> Sequence[Product]:
        """Fetch products with pagination.
        
        Args:
            limit: Maximum number of products to return
            offset: Number of products to skip
            
        Returns:
            Sequence of Product instances
        """
        return (
            self._session.query(Product)
            .order_by(Product.created_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    def count(self) -> int:
        """Return total number of products in the database.
        
        Returns:
            Total product count
        """
        return self._session.query(Product).count()

