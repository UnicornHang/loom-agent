from fastapi import APIRouter

from app.api.v1.routes import auth, health, hotspots, product_groups, products, users, workflows

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(product_groups.router)
api_router.include_router(hotspots.router)
api_router.include_router(products.router)
api_router.include_router(workflows.router)
