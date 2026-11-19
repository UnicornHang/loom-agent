from sqlalchemy import Select, exists, select
from sqlalchemy.orm import Session

from app.models import Product, ProductGrant, ProductGroup, User


def visible_products(user: User) -> Select[tuple[Product]]:
    query = select(Product).where(Product.tenant_id == user.tenant_id)
    if user.role != "admin":
        grant_exists = exists(select(ProductGrant.id).where(
            ProductGrant.group_id == Product.group_id,
            ProductGrant.user_id == user.id,
        ))
        query = query.where(grant_exists)
    return query


def can_manage_group(db: Session, user: User, group_id: str) -> bool:
    group = db.get(ProductGroup, group_id)
    if group is None or group.tenant_id != user.tenant_id:
        return False
    if user.role == "admin":
        return True
    return user.role == "product_manager" and db.scalar(select(ProductGrant.id).where(
        ProductGrant.user_id == user.id, ProductGrant.group_id == group_id,
    )) is not None
