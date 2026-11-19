from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import User
from app.security import hash_password


def test_login_permissions_and_workflow():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)

    def test_db():
        with Session(engine) as session:
            yield session

    with Session(engine) as db:
        db.add(User(username="admin", password_hash=hash_password("AdminPassword123!"), role="admin"))
        db.commit()

    app.dependency_overrides[get_db] = test_db
    try:
        admin = TestClient(app)
        creator = TestClient(app)
        assert admin.get("/api/v1/products").status_code == 401
        assert admin.post("/api/v1/auth/login", json={"username": "admin", "password": "wrong"}).status_code == 401
        assert admin.post("/api/v1/auth/login", json={"username": "admin", "password": "AdminPassword123!"}).status_code == 200
        admin_csrf = {"X-CSRF-Token": admin.cookies["loom_csrf"]}
        assert admin.post("/api/v1/product-groups", json={"name": "耳机"}).status_code == 403

        group = admin.post("/api/v1/product-groups", json={"name": "耳机"}, headers=admin_csrf)
        assert group.status_code == 201
        group_id = group.json()["id"]
        user = admin.post("/api/v1/users", json={"username": "creator", "password": "CreatorPassword123!", "role": "creator"}, headers=admin_csrf)
        assert user.status_code == 201
        user_id = user.json()["id"]
        manager_user = admin.post("/api/v1/users", json={"username": "manager", "password": "ManagerPassword123!", "role": "product_manager"}, headers=admin_csrf)
        assert manager_user.status_code == 201
        assert creator.post("/api/v1/auth/login", json={"username": "creator", "password": "CreatorPassword123!"}).status_code == 200
        creator_csrf = {"X-CSRF-Token": creator.cookies["loom_csrf"]}

        product = admin.post("/api/v1/products", json={"sku": "EAR-001", "name": "开放式耳机", "category": "耳机", "group_id": group_id}, headers=admin_csrf)
        assert product.status_code == 201
        product_id = product.json()["id"]
        assert creator.get("/api/v1/products").json() == []
        assert creator.get(f"/api/v1/products/{product_id}").status_code == 404
        assert creator.post("/api/v1/products", json={"sku": "EAR-002", "name": "无权创建", "category": "耳机", "group_id": group_id}, headers=creator_csrf).status_code == 403

        manager = TestClient(app)
        assert manager.post("/api/v1/auth/login", json={"username": "manager", "password": "ManagerPassword123!"}).status_code == 200
        manager_csrf = {"X-CSRF-Token": manager.cookies["loom_csrf"]}
        assert manager.post("/api/v1/products", json={"sku": "EAR-002", "name": "未授权", "category": "耳机", "group_id": group_id}, headers=manager_csrf).status_code == 403
        assert admin.post(f"/api/v1/product-groups/{group_id}/grants", json={"user_id": manager_user.json()["id"]}, headers=admin_csrf).status_code == 201
        assert manager.post("/api/v1/products", json={"sku": "EAR-002", "name": "有权维护", "category": "耳机", "group_id": group_id}, headers=manager_csrf).status_code == 201

        assert admin.post(f"/api/v1/product-groups/{group_id}/grants", json={"user_id": user_id}, headers=admin_csrf).status_code == 201
        assert len(creator.get("/api/v1/products").json()) == 2
        hotspot = creator.post("/api/v1/hotspots", json={"title": "耳机种草内容", "content_type": "article"}, headers=creator_csrf)
        assert hotspot.status_code == 201
        workflow = creator.post("/api/v1/workflows", json={"hotspot_id": hotspot.json()["id"]}, headers=creator_csrf)
        assert workflow.status_code == 201
        assert len(creator.get(f"/api/v1/workflows/{workflow.json()['id']}/events").json()) == 1
        assert creator.post(f"/api/v1/workflows/{workflow.json()['id']}/run", headers=creator_csrf).status_code == 503

        assert admin.delete(f"/api/v1/product-groups/{group_id}/grants/{user_id}", headers=admin_csrf).status_code == 200
        assert creator.get("/api/v1/products").json() == []
        assert admin.patch(f"/api/v1/users/{user_id}/active", json={"is_active": False}, headers=admin_csrf).status_code == 200
        assert creator.get("/api/v1/auth/me").status_code == 401
        assert admin.post("/api/v1/auth/change-password", json={"current_password": "wrong", "new_password": "NewPassword123!"}, headers=admin_csrf).status_code == 400
        assert admin.post("/api/v1/auth/change-password", json={"current_password": "AdminPassword123!", "new_password": "NewPassword123!"}, headers=admin_csrf).status_code == 200
        assert admin.get("/api/v1/auth/me").status_code == 401
        assert admin.post("/api/v1/auth/login", json={"username": "admin", "password": "NewPassword123!"}).status_code == 200
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
