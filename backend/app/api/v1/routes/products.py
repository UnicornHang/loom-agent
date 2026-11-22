from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import select, or_, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Product, ProductGroup, User
from app.schemas import ProductCreate, ProductGroupUpdate, ProductRead, ProductUpdate
from app.security import current_user, require_csrf, require_roles
from app.services.product_access import can_manage_group, visible_products

router = APIRouter(prefix="/products", tags=["products"])


@router.get("", response_model=list[ProductRead])
def list_products(q: str = Query(default="", max_length=200),
                  product_status: str | None = None,
                  db: Session = Depends(get_db), user: User = Depends(current_user)):
    query = visible_products(user)
    if q.strip():
        term = '%' + q.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        query = query.where(or_(Product.name.ilike(term, escape='\\'), Product.sku.ilike(term, escape='\\'), Product.category.ilike(term, escape='\\')))
    if product_status:
        query = query.where(Product.status == product_status)
    return db.scalars(query.order_by(Product.created_at.desc())).all()


@router.put("/{product_id}", response_model=ProductRead, dependencies=[Depends(require_csrf)])
def update_product(product_id: str, payload: ProductUpdate, db: Session = Depends(get_db),
                   user: User = Depends(require_roles("admin", "product_manager"))):
    product = db.scalar(visible_products(user).where(Product.id == product_id))
    if product is None:
        raise HTTPException(404, "产品不存在")
    if not product.group_id or not can_manage_group(db, user, product.group_id):
        raise HTTPException(403, "没有该产品的维护权限")
    if payload.status == 'active' and not payload.description.strip():
        raise HTTPException(422, "启用前请补充已核实的产品描述")
    result = db.execute(update(Product).where(Product.id == product_id,
        Product.name == payload.expected_name, Product.category == payload.expected_category,
        Product.description == payload.expected_description, Product.status == payload.expected_status).values(
        **payload.model_dump(exclude={'expected_name', 'expected_category', 'expected_description', 'expected_status'})))
    if not result.rowcount:
        db.rollback()
        raise HTTPException(409, "产品已被其他成员修改，请刷新后重试")
    db.commit()
    db.refresh(product)
    return product


@router.get("/{product_id}", response_model=ProductRead)
def get_product(product_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    product = db.scalar(visible_products(user).where(Product.id == product_id))
    if product is None:
        raise HTTPException(status_code=404, detail="产品不存在")
    return product


@router.post("", response_model=ProductRead, status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(require_csrf)])
def create_product(payload: ProductCreate, db: Session = Depends(get_db),
                   user: User = Depends(require_roles("admin", "product_manager"))):
    if not payload.group_id or not can_manage_group(db, user, payload.group_id):
        raise HTTPException(status_code=403, detail="没有该产品分组的维护权限")
    product = Product(**payload.model_dump(), tenant_id=user.tenant_id)
    db.add(product)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="SKU 已存在") from None
    db.refresh(product)
    return product


@router.patch("/{product_id}/group", response_model=ProductRead,
              dependencies=[Depends(require_csrf)])
def assign_product_group(product_id: str, payload: ProductGroupUpdate, db: Session = Depends(get_db),
                         admin: User = Depends(require_roles("admin"))):
    product = db.get(Product, product_id)
    group = db.get(ProductGroup, payload.group_id)
    if product is None or product.tenant_id != admin.tenant_id:
        raise HTTPException(status_code=404, detail="产品不存在")
    if group is None or group.tenant_id != admin.tenant_id:
        raise HTTPException(status_code=404, detail="分组不存在")
    product.group_id = group.id
    db.commit()
    db.refresh(product)
    return product
