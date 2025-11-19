"""Tests for ProductRepository."""
from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from app.models.product import Product
from app.schemas.product import ProductCreate
from app.services.product_repository import ProductRepository


class TestProductRepository:
    """Test suite for ProductRepository."""

    def test_batch_upsert_insert_new_products(self, db_session: Session) -> None:
        """Test batch inserting new products."""
        repo = ProductRepository(db_session)
        
        products = [
            ProductCreate(sku="SKU-001", name="Product 1", description="Desc 1", active=True),
            ProductCreate(sku="SKU-002", name="Product 2", description="Desc 2", active=True),
            ProductCreate(sku="SKU-003", name="Product 3", description=None, active=False),
        ]
        
        rows_affected = repo.batch_upsert(products)
        
        assert rows_affected == 3
        
        # Verify products were inserted
        all_products = db_session.query(Product).all()
        assert len(all_products) == 3
        assert all_products[0].sku == "SKU-001"
        assert all_products[1].sku == "SKU-002"
        assert all_products[2].sku == "SKU-003"

    def test_batch_upsert_update_existing_products(self, db_session: Session) -> None:
        """Test batch updating existing products."""
        repo = ProductRepository(db_session)
        
        # Insert initial products
        initial_products = [
            ProductCreate(sku="SKU-001", name="Product 1", description="Old Desc", active=True),
            ProductCreate(sku="SKU-002", name="Product 2", description="Old Desc", active=True),
        ]
        repo.batch_upsert(initial_products)
        
        # Update with new data
        updated_products = [
            ProductCreate(sku="SKU-001", name="Updated Product 1", description="New Desc", active=False),
            ProductCreate(sku="SKU-002", name="Updated Product 2", description="New Desc", active=False),
        ]
        rows_affected = repo.batch_upsert(updated_products)
        
        assert rows_affected == 2
        
        # Verify products were updated
        product1 = db_session.query(Product).filter_by(sku="SKU-001").first()
        assert product1.name == "Updated Product 1"
        assert product1.description == "New Desc"
        assert product1.active is False
        
        product2 = db_session.query(Product).filter_by(sku="SKU-002").first()
        assert product2.name == "Updated Product 2"

    def test_batch_upsert_case_insensitive_sku(self, db_session: Session) -> None:
        """Test that SKU matching is case-insensitive."""
        repo = ProductRepository(db_session)
        
        # Insert with lowercase SKU
        initial = [ProductCreate(sku="sku-001", name="Product 1", active=True)]
        repo.batch_upsert(initial)
        
        # Update with uppercase SKU - should update, not insert
        updated = [ProductCreate(sku="SKU-001", name="Updated Product", active=False)]
        rows_affected = repo.batch_upsert(updated)
        
        assert rows_affected == 1
        
        # Should still be only 1 product
        all_products = db_session.query(Product).all()
        assert len(all_products) == 1
        assert all_products[0].name == "Updated Product"
        assert all_products[0].active is False

    def test_batch_upsert_mixed_insert_and_update(self, db_session: Session) -> None:
        """Test batch upsert with mix of new and existing products."""
        repo = ProductRepository(db_session)
        
        # Insert initial product
        initial = [ProductCreate(sku="SKU-001", name="Product 1", active=True)]
        repo.batch_upsert(initial)
        
        # Batch with update + insert
        mixed = [
            ProductCreate(sku="SKU-001", name="Updated Product 1", active=False),
            ProductCreate(sku="SKU-002", name="New Product 2", active=True),
            ProductCreate(sku="SKU-003", name="New Product 3", active=True),
        ]
        rows_affected = repo.batch_upsert(mixed)
        
        assert rows_affected == 3
        
        # Verify correct products exist
        all_products = db_session.query(Product).order_by(Product.sku).all()
        assert len(all_products) == 3
        assert all_products[0].name == "Updated Product 1"  # Updated
        assert all_products[1].name == "New Product 2"  # Inserted
        assert all_products[2].name == "New Product 3"  # Inserted

    def test_batch_upsert_empty_list(self, db_session: Session) -> None:
        """Test batch upsert with empty list returns 0."""
        repo = ProductRepository(db_session)
        
        rows_affected = repo.batch_upsert([])
        
        assert rows_affected == 0
        assert db_session.query(Product).count() == 0

    def test_batch_upsert_preserves_created_at(self, db_session: Session) -> None:
        """Test that updating a product preserves the created_at timestamp."""
        repo = ProductRepository(db_session)
        
        # Insert initial product
        initial = [ProductCreate(sku="SKU-001", name="Product 1", active=True)]
        repo.batch_upsert(initial)
        
        product = db_session.query(Product).filter_by(sku="SKU-001").first()
        original_created_at = product.created_at
        
        # Update the product
        updated = [ProductCreate(sku="SKU-001", name="Updated Product", active=False)]
        repo.batch_upsert(updated)
        
        # Verify created_at is unchanged
        product = db_session.query(Product).filter_by(sku="SKU-001").first()
        assert product.created_at == original_created_at
        assert product.name == "Updated Product"

    def test_get_by_sku_case_insensitive(self, db_session: Session) -> None:
        """Test fetching product by SKU is case-insensitive."""
        repo = ProductRepository(db_session)
        
        # Insert with lowercase
        products = [ProductCreate(sku="sku-test", name="Test Product", active=True)]
        repo.batch_upsert(products)
        
        # Query with uppercase should still find it
        product = repo.get_by_sku("SKU-TEST")
        assert product is not None
        assert product.name == "Test Product"
        
        # Query with mixed case
        product = repo.get_by_sku("Sku-Test")
        assert product is not None

    def test_get_by_sku_not_found(self, db_session: Session) -> None:
        """Test get_by_sku returns None when SKU doesn't exist."""
        repo = ProductRepository(db_session)
        
        product = repo.get_by_sku("NONEXISTENT")
        assert product is None

    def test_get_by_id(self, db_session: Session) -> None:
        """Test fetching product by database ID."""
        repo = ProductRepository(db_session)
        
        products = [ProductCreate(sku="SKU-001", name="Product 1", active=True)]
        repo.batch_upsert(products)
        
        # Get the product to find its ID
        product = db_session.query(Product).filter_by(sku="SKU-001").first()
        product_id = product.id
        
        # Fetch by ID
        found = repo.get_by_id(product_id)
        assert found is not None
        assert found.sku == "SKU-001"

    def test_get_by_id_not_found(self, db_session: Session) -> None:
        """Test get_by_id returns None when ID doesn't exist."""
        repo = ProductRepository(db_session)
        
        product = repo.get_by_id(99999)
        assert product is None

    def test_get_all_pagination(self, db_session: Session) -> None:
        """Test get_all with pagination."""
        repo = ProductRepository(db_session)
        
        # Insert 25 products
        products = [
            ProductCreate(sku=f"SKU-{i:03d}", name=f"Product {i}", active=True)
            for i in range(1, 26)
        ]
        repo.batch_upsert(products)
        
        # Get first page
        page1 = repo.get_all(limit=10, offset=0)
        assert len(page1) == 10
        
        # Get second page
        page2 = repo.get_all(limit=10, offset=10)
        assert len(page2) == 10
        
        # Get third page
        page3 = repo.get_all(limit=10, offset=20)
        assert len(page3) == 5

    def test_count(self, db_session: Session) -> None:
        """Test counting total products."""
        repo = ProductRepository(db_session)
        
        assert repo.count() == 0
        
        # Insert products
        products = [
            ProductCreate(sku=f"SKU-{i:03d}", name=f"Product {i}", active=True)
            for i in range(1, 6)
        ]
        repo.batch_upsert(products)
        
        assert repo.count() == 5

    def test_batch_upsert_with_none_description(self, db_session: Session) -> None:
        """Test batch upsert handles None descriptions correctly."""
        repo = ProductRepository(db_session)
        
        products = [
            ProductCreate(sku="SKU-001", name="Product 1", description=None, active=True),
            ProductCreate(sku="SKU-002", name="Product 2", description="Has description", active=True),
        ]
        repo.batch_upsert(products)
        
        product1 = db_session.query(Product).filter_by(sku="SKU-001").first()
        assert product1.description is None
        
        product2 = db_session.query(Product).filter_by(sku="SKU-002").first()
        assert product2.description == "Has description"

    def test_batch_upsert_large_batch(self, db_session: Session) -> None:
        """Test batch upsert with large number of products."""
        repo = ProductRepository(db_session)
        
        # Insert 1000 products
        products = [
            ProductCreate(sku=f"SKU-{i:05d}", name=f"Product {i}", active=True)
            for i in range(1, 1001)
        ]
        rows_affected = repo.batch_upsert(products)
        
        assert rows_affected == 1000
        assert repo.count() == 1000

