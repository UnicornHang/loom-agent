"""Private product images; every read rechecks current product grants."""
from io import BytesIO
from uuid import uuid4

import boto3
from botocore.exceptions import ClientError
from PIL import Image, UnidentifiedImageError
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Product, User
from app.security import current_user, require_csrf
from app.services.product_access import visible_products, can_manage_group

router = APIRouter(prefix="/products/{product_id}/images", tags=["product-images"])
LIMIT = 10 * 1024 * 1024


def storage():
    return boto3.client("s3", endpoint_url=settings.object_storage_endpoint,
                        aws_access_key_id=settings.object_storage_access_key,
                        aws_secret_access_key=settings.object_storage_secret_key)


def product_access(product_id: str, db: Session, user: User, write=False):
    product = db.scalar(visible_products(user).where(Product.id == product_id))
    if product is None:
        raise HTTPException(404, "产品不存在")
    if write and not (user.role == "admin" or (product.group_id and can_manage_group(db, user, product.group_id))):
        raise HTTPException(403, "没有素材维护权限")
    return f"{user.tenant_id}/{product.id}/"


@router.get("")
def list_images(product_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    prefix = product_access(product_id, db, user)
    client = storage()
    try:
        pages = client.get_paginator("list_objects_v2").paginate(Bucket=settings.object_storage_bucket, Prefix=prefix)
        return [{"id": item["Key"].removeprefix(prefix), "size": item["Size"]} for page in pages for item in page.get("Contents", [])]
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "NoSuchBucket":
            return []
        raise HTTPException(503, "素材存储暂不可用") from None


@router.post("", dependencies=[Depends(require_csrf)])
async def upload_image(product_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    prefix = product_access(product_id, db, user, write=True)
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > LIMIT:
            raise HTTPException(413, "图片不能超过 10 MB")
    try:
        with Image.open(BytesIO(body)) as picture:
            if picture.format not in {"JPEG", "PNG", "WEBP"} or picture.width * picture.height > 25_000_000:
                raise ValueError()
            picture.load()
            output = BytesIO()
            picture.convert("RGB").save(output, format="JPEG", quality=92)
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        raise HTTPException(400, "请上传有效的 JPG、PNG 或 WebP 图片，最多 2500 万像素") from None
    client = storage()
    try:
        client.create_bucket(Bucket=settings.object_storage_bucket)
    except ClientError as exc:
        if exc.response["Error"]["Code"] not in {"BucketAlreadyOwnedByYou", "BucketAlreadyExists"}:
            raise HTTPException(503, "素材存储暂不可用") from None
    image_id = uuid4().hex + ".jpg"
    client.put_object(Bucket=settings.object_storage_bucket, Key=prefix + image_id, Body=output.getvalue(), ContentType="image/jpeg")
    return {"id": image_id}


@router.get("/{image_id}")
def read_image(product_id: str, image_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    prefix = product_access(product_id, db, user)
    if len(image_id) != 36 or not image_id.endswith(".jpg") or any(c not in "0123456789abcdef" for c in image_id[:32]):
        raise HTTPException(404, "图片不存在")
    try:
        result = storage().get_object(Bucket=settings.object_storage_bucket, Key=prefix + image_id)
        with result["Body"] as stream:
            return Response(stream.read(), media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})
    except ClientError:
        raise HTTPException(404, "图片不存在") from None


@router.delete("/{image_id}", dependencies=[Depends(require_csrf)])
def delete_image(product_id: str, image_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    prefix = product_access(product_id, db, user, write=True)
    if len(image_id) != 36 or not image_id.endswith(".jpg") or any(c not in "0123456789abcdef" for c in image_id[:32]):
        raise HTTPException(404, "图片不存在")
    storage().delete_object(Bucket=settings.object_storage_bucket, Key=prefix + image_id)
    return {"ok": True}
