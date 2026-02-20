import logging
import uuid
from typing import List

from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database import get_db
from app.core.exceptions import BusinessValidationError, NotFoundError
from app.models.part import Part, PartCategory
from app.schemas.part import PartCategoryCreate, PartCategoryRead, PartCategoryUpdate

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/part-categories",
    tags=["Categorie Ricambi"],
)


@router.get("/", response_model=List[PartCategoryRead])
async def get_all_categories(db: AsyncSession = Depends(get_db)):
    """Recupera tutte le categorie (con subcategorie annidate)."""
    # Fetch root categories (without parent). selectinload will fetch nested children natively because of lazy="selectin" on children relationship.
    query = (
        select(PartCategory)
        .where(PartCategory.parent_id == None)
        .where(PartCategory.is_active == True)
        .order_by(PartCategory.name)
    )
    result = await db.execute(query)
    categories = result.scalars().all()
    return categories


@router.get("/{category_id}", response_model=PartCategoryRead)
async def get_category(category_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Recupera il dettaglio di una categoria."""
    query = select(PartCategory).where(PartCategory.id == category_id)
    result = await db.execute(query)
    category = result.scalar_one_or_none()
    
    if not category:
        raise NotFoundError(f"Categoria {category_id} non trovata")
        
    return category


@router.post("/", response_model=PartCategoryRead, status_code=status.HTTP_201_CREATED)
async def create_category(data: PartCategoryCreate, db: AsyncSession = Depends(get_db)):
    """Crea una nuova categoria."""
    if data.parent_id:
        parent = await db.execute(select(PartCategory).where(PartCategory.id == data.parent_id))
        if not parent.scalar_one_or_none():
            raise NotFoundError(f"Categoria padre {data.parent_id} non trovata")
    
    category = PartCategory(**data.model_dump())
    db.add(category)
    await db.commit()
    await db.refresh(category)
    return category


@router.put("/{category_id}", response_model=PartCategoryRead)
async def update_category(category_id: uuid.UUID, data: PartCategoryUpdate, db: AsyncSession = Depends(get_db)):
    """Aggiorna una categoria."""
    query = select(PartCategory).where(PartCategory.id == category_id)
    result = await db.execute(query)
    category = result.scalar_one_or_none()
    
    if not category:
        raise NotFoundError(f"Categoria {category_id} non trovata")
        
    if data.parent_id:
        if data.parent_id == category_id:
            raise BusinessValidationError("Una categoria non può essere padre di se stessa")
        parent = await db.execute(select(PartCategory).where(PartCategory.id == data.parent_id))
        if not parent.scalar_one_or_none():
            raise NotFoundError(f"Categoria padre {data.parent_id} non trovata")
            
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(category, k, v)
        
    await db.commit()
    await db.refresh(category)
    return category


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_category(category_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Soft delete di una categoria. Blocca se ha ricambi attivi associati."""
    query = select(PartCategory).where(PartCategory.id == category_id)
    result = await db.execute(query)
    category = result.scalar_one_or_none()
    
    if not category:
        raise NotFoundError(f"Categoria {category_id} non trovata")
        
    # Verifica ricambi associati
    parts_query = select(func.count(Part.id)).where(Part.category_id == category_id, Part.is_active == True)
    parts_count = await db.execute(parts_query)
    if (parts_count.scalar() or 0) > 0:
        raise BusinessValidationError("Impossibile eliminare categoria: ci sono ricambi attivi associati")
        
    category.is_active = False
    await db.commit()
