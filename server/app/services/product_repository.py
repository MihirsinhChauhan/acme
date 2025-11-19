"""Product repository for batch operations and database access."""
from __future__ import annotations

from typing import Sequence, Any

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.product import Product
from app.schemas.product import ProductCreate, ProductUpdate, ProductFilter


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

        # Deduplicate products by case-insensitive SKU within the batch
        # Keep the last occurrence of each SKU (latest data wins)
        # Build dicts directly to avoid second iteration
        seen_skus: dict[str, dict[str, Any]] = {}
        for product in products:
            # Normalize SKU to lowercase for deduplication
            # Skip if SKU is empty (shouldn't happen, but safety check)
            if not product.sku or not product.sku.strip():
                continue
            sku_key = product.sku.strip().lower()
            seen_skus[sku_key] = {
                "sku": product.sku.strip(),  # Also strip the stored SKU
                "name": product.name,
                "description": product.description,
                "active": product.active,
            }
        
        # Use deduplicated product dicts directly
        product_dicts = list(seen_skus.values())

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

    def list_with_filters(
        self, filter_params: ProductFilter, page: int = 1, page_size: int = 20
    ) -> tuple[Sequence[Product], int]:
        """Fetch products with filtering and pagination.
        
        Args:
            filter_params: ProductFilter instance with optional filters
            page: Page number (1-indexed)
            page_size: Number of items per page
            
        Returns:
            Tuple of (products sequence, total count)
        """
        query = self._session.query(Product)
        
        # Apply filters with ILIKE for partial matching (case-insensitive)
        if filter_params.sku is not None:
            query = query.filter(Product.sku.ilike(f"%{filter_params.sku}%"))
        
        if filter_params.name is not None:
            query = query.filter(Product.name.ilike(f"%{filter_params.name}%"))
        
        if filter_params.description is not None:
            # Handle NULL descriptions - only match non-NULL descriptions
            query = query.filter(
                Product.description.isnot(None),
                Product.description.ilike(f"%{filter_params.description}%"),
            )
        
        if filter_params.active is not None:
            query = query.filter(Product.active == filter_params.active)
        
        # Get total count before pagination
        total = query.count()
        
        # Apply pagination
        offset = (page - 1) * page_size
        products = (
            query.order_by(Product.created_at.desc())
            .limit(page_size)
            .offset(offset)
            .all()
        )
        
        return products, total

    def create(self, product: ProductCreate) -> Product:
        """Create a new product.
        
        Args:
            product: ProductCreate schema with product data
            
        Returns:
            Created Product instance
            
        Raises:
            IntegrityError: If SKU already exists (case-insensitive)
        """
        db_product = Product(
            sku=product.sku.strip(),
            name=product.name,
            description=product.description,
            active=product.active,
        )
        self._session.add(db_product)
        self._session.commit()
        self._session.refresh(db_product)
        return db_product

    def update(self, product_id: int, product: ProductUpdate) -> Product | None:
        """Update a product by ID.
        
        Args:
            product_id: Database identifier
            product: ProductUpdate schema with fields to update
            
        Returns:
            Updated Product instance if found, None otherwise
            
        Raises:
            IntegrityError: If new SKU already exists (case-insensitive)
        """
        db_product = self.get_by_id(product_id)
        if db_product is None:
            return None
        
        # Update only provided fields
        if product.sku is not None:
            db_product.sku = product.sku.strip()
        if product.name is not None:
            db_product.name = product.name
        if product.description is not None:
            db_product.description = product.description
        if product.active is not None:
            db_product.active = product.active
        
        self._session.commit()
        self._session.refresh(db_product)
        return db_product

    def delete(self, product_id: int) -> bool:
        """Delete a product by ID.
        
        Args:
            product_id: Database identifier
            
        Returns:
            True if product was deleted, False if not found
        """
        db_product = self.get_by_id(product_id)
        if db_product is None:
            return False
        
        self._session.delete(db_product)
        self._session.commit()
        return True

