"""Product management and bulk operations API endpoints."""
from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_session
from app.schemas.product import (
    ProductCreate,
    ProductFilter,
    ProductListResponse,
    ProductResponse,
    ProductUpdate,
)
from app.services.import_service import ImportService
from app.services.product_repository import ProductRepository
from app.services.webhook_service import WebhookService

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/products", tags=["products"])


def get_product_repository(session: Session = Depends(get_session)) -> ProductRepository:
    """Dependency to get ProductRepository instance."""
    return ProductRepository(session)


class BulkDeleteResponse(BaseModel):
    """Response payload after initiating bulk delete operation."""

    job_id: str
    sse_url: str
    message: str


@router.get(
    "",
    response_model=ProductListResponse,
    status_code=status.HTTP_200_OK,
    summary="List products with filtering and pagination",
    description=(
        "Retrieve a paginated list of products with optional filtering by SKU, name, "
        "description, and active status. All text filters use case-insensitive partial matching."
    ),
)
async def list_products(
    sku: str | None = Query(default=None, description="Filter by SKU (partial match)"),
    name: str | None = Query(default=None, description="Filter by name (partial match)"),
    description: str | None = Query(default=None, description="Filter by description (partial match)"),
    active: bool | None = Query(default=None, description="Filter by active status"),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page (max 100)"),
    repository: ProductRepository = Depends(get_product_repository),
) -> ProductListResponse:
    """
    List products with optional filters and pagination.

    Args:
        sku: Optional SKU filter (partial match, case-insensitive)
        name: Optional name filter (partial match, case-insensitive)
        description: Optional description filter (partial match, case-insensitive)
        active: Optional active status filter
        page: Page number (default: 1)
        page_size: Items per page (default: 20, max: 100)
        repository: ProductRepository instance (injected)

    Returns:
        ProductListResponse with items, total, page, and page_size
    """
    filter_params = ProductFilter(sku=sku, name=name, description=description, active=active)
    products, total = repository.list_with_filters(filter_params, page=page, page_size=page_size)

    return ProductListResponse(
        items=[ProductResponse.model_validate(p) for p in products],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post(
    "",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new product",
    description="Create a new product. SKU must be unique (case-insensitive).",
)
async def create_product(
    product: ProductCreate,
    session: Session = Depends(get_session),
    repository: ProductRepository = Depends(get_product_repository),
) -> ProductResponse:
    """
    Create a new product.

    Args:
        product: ProductCreate schema with product data
        repository: ProductRepository instance (injected)

    Returns:
        Created ProductResponse

    Raises:
        HTTPException: 409 if SKU already exists (case-insensitive)
    """
    try:
        created_product = repository.create(product)
        
        # Publish webhook event
        try:
            webhook_service = WebhookService(session)
            product_dict = ProductResponse.model_validate(created_product).model_dump()
            webhook_service.publish_event("product.created", product_dict)
        except Exception as webhook_err:
            logger.warning(f"Failed to publish webhook event for product.created: {webhook_err}")
            # Don't fail the request if webhook fails
        
        return ProductResponse.model_validate(created_product)
    except Exception as e:
        # Check if it's a unique constraint violation
        error_str = str(e).lower()
        if "unique" in error_str or "duplicate" in error_str or "constraint" in error_str:
            logger.warning(f"Attempted to create product with duplicate SKU: {product.sku}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Product with SKU '{product.sku}' already exists",
            ) from e
        logger.exception(f"Unexpected error creating product: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create product",
        ) from e


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Get product by ID",
    description="Retrieve a single product by its database ID.",
)
async def get_product(
    product_id: int,
    repository: ProductRepository = Depends(get_product_repository),
) -> ProductResponse:
    """
    Get a product by ID.

    Args:
        product_id: Database identifier
        repository: ProductRepository instance (injected)

    Returns:
        ProductResponse

    Raises:
        HTTPException: 404 if product not found
    """
    product = repository.get_by_id(product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found",
        )
    return ProductResponse.model_validate(product)


@router.put(
    "/{product_id}",
    response_model=ProductResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a product (full update)",
    description=(
        "Update a product by ID. All fields in ProductUpdate are optional. "
        "Only provided fields will be updated. SKU must remain unique (case-insensitive)."
    ),
)
async def update_product(
    product_id: int,
    product: ProductUpdate,
    session: Session = Depends(get_session),
    repository: ProductRepository = Depends(get_product_repository),
) -> ProductResponse:
    """
    Update a product by ID.

    Args:
        product_id: Database identifier
        product: ProductUpdate schema with fields to update
        repository: ProductRepository instance (injected)

    Returns:
        Updated ProductResponse

    Raises:
        HTTPException: 404 if product not found, 409 if new SKU conflicts
    """
    try:
        updated_product = repository.update(product_id, product)
        if updated_product is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product with ID {product_id} not found",
            )
        
        # Publish webhook event
        try:
            webhook_service = WebhookService(session)
            product_dict = ProductResponse.model_validate(updated_product).model_dump()
            webhook_service.publish_event("product.updated", product_dict)
        except Exception as webhook_err:
            logger.warning(f"Failed to publish webhook event for product.updated: {webhook_err}")
            # Don't fail the request if webhook fails
        
        return ProductResponse.model_validate(updated_product)
    except HTTPException:
        raise
    except Exception as e:
        # Check if it's a unique constraint violation
        error_str = str(e).lower()
        if "unique" in error_str or "duplicate" in error_str or "constraint" in error_str:
            logger.warning(f"Attempted to update product {product_id} with duplicate SKU")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="SKU already exists (case-insensitive)",
            ) from e
        logger.exception(f"Unexpected error updating product {product_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update product",
        ) from e


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a product by ID",
    description="Delete a product by its database ID. Returns 204 No Content on success.",
)
async def delete_product(
    product_id: int,
    session: Session = Depends(get_session),
    repository: ProductRepository = Depends(get_product_repository),
) -> None:
    """
    Delete a product by ID.

    Args:
        product_id: Database identifier
        repository: ProductRepository instance (injected)

    Raises:
        HTTPException: 404 if product not found
    """
    # Get product before deletion for webhook payload
    product = repository.get_by_id(product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found",
        )
    
    deleted = repository.delete(product_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with ID {product_id} not found",
        )
    
    # Publish webhook event
    try:
        webhook_service = WebhookService(session)
        product_dict = ProductResponse.model_validate(product).model_dump()
        webhook_service.publish_event("product.deleted", product_dict)
    except Exception as webhook_err:
        logger.warning(f"Failed to publish webhook event for product.deleted: {webhook_err}")
        # Don't fail the request if webhook fails


@router.post(
    "/bulk-delete",
    response_model=BulkDeleteResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Bulk delete all products",
    description=(
        "Initiates an asynchronous bulk deletion of all products in the database. "
        "Returns immediately with job_id and SSE URL for progress tracking. "
        "Products are deleted in batches to ensure efficient processing."
    ),
)
async def bulk_delete_all_products(
    session: Session = Depends(get_session),
) -> BulkDeleteResponse:
    """
    Initiate bulk deletion of all products.

    Steps:
    1. Create a bulk delete job record in database
    2. Enqueue Celery task for background processing
    3. Return job_id and SSE URL for progress tracking

    Args:
        session: Database session (injected)

    Returns:
        BulkDeleteResponse with job_id and sse_url

    Raises:
        HTTPException: 500 on unexpected errors
    """
    try:
        # Step 1: Create delete job record in database
        logger.info("Creating bulk delete job")
        import_service = ImportService(session)
        job_response = import_service.create_delete_job()

        logger.info(f"Bulk delete job created: {job_response.id}")

        # Step 2: Enqueue Celery task for background processing
        logger.info(f"Enqueueing bulk delete task for job_id: {job_response.id}")
        task_id = import_service.enqueue_delete_task(job_id=job_response.id)

        logger.info(
            f"Task enqueued successfully - job_id: {job_response.id}, task_id: {task_id}"
        )

        # Step 3: Return response with job_id and SSE URL
        sse_url = f"{settings.api_prefix}/progress/{job_response.id}"
        
        # Note: Webhook event for bulk delete will be published when the task completes
        # (handled in bulk_delete_tasks.py)
        
        return BulkDeleteResponse(
            job_id=str(job_response.id),
            sse_url=sse_url,
            message="Bulk delete operation initiated. All products will be deleted in the background.",
        )

    except Exception as e:
        # Log error with context
        logger.exception(f"Unexpected error during bulk delete initiation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate bulk delete: {str(e)}",
        )
