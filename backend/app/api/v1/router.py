from fastapi import APIRouter
from app.api.v1.routes import recommendations
from app.api.v1.routes import workflow_entry
from app.api.v1.routes import workflow_assets
from app.api.v1.routes import audit
from app.api.v1.routes import mcp_servers
from app.api.v1.routes import skills
from app.api.v1.routes import sources
from app.api.v1.routes import agent_runs
from app.api.v1.routes import budgets
from app.api.v1.routes import workspaces
from app.api.v1.routes import agent_configs
from app.api.v1.routes import model_connections
from app.api.v1.routes import product_assets

from app.api.v1.routes import auth, health, hotspots, product_groups, products, users, workflows

api_router = APIRouter()
api_router.include_router(recommendations.router)
api_router.include_router(workflow_entry.router)
api_router.include_router(workflow_assets.router)
api_router.include_router(audit.router)
api_router.include_router(mcp_servers.router)
api_router.include_router(skills.router)
api_router.include_router(sources.router)
api_router.include_router(agent_runs.router)
api_router.include_router(budgets.router)
api_router.include_router(workspaces.router)
api_router.include_router(agent_configs.router)
api_router.include_router(model_connections.router)
api_router.include_router(product_assets.router)
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(product_groups.router)
api_router.include_router(hotspots.router)
api_router.include_router(products.router)
api_router.include_router(workflows.router)
