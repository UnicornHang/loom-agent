from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import User
from app.security import hash_password


def test_login_permissions_and_workflow(monkeypatch):
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
        source_payload = {'name': '待授权来源', 'adapter': 'douyin_official', 'industry': '3C', 'keywords': [], 'enabled': True, 'interval_minutes': 60}
        assert creator.post('/api/v1/sources', json=source_payload, headers=creator_csrf).status_code == 403
        assert admin.post('/api/v1/sources', json={**source_payload, 'interval_minutes': 0}, headers=admin_csrf).status_code == 422
        source = admin.post('/api/v1/sources', json=source_payload, headers=admin_csrf)
        assert source.status_code == 201
        source_id = source.json()['id']
        assert admin.post(f'/api/v1/sources/{source_id}/run', headers=admin_csrf).json()['status'] == 'blocked'
        from app.services.collection_scheduler import dispatch_due
        with Session(engine) as db:
            assert dispatch_due(db) == 1
            assert dispatch_due(db) == 0
        assert len(admin.get(f'/api/v1/sources/{source_id}/runs').json()) == 2
        assert admin.get('/api/v1/hotspots').json() == []
        assert admin.put(f'/api/v1/sources/{source_id}', json={**source_payload, 'revision': 0}, headers=admin_csrf).status_code == 409
        assert admin.put(f'/api/v1/sources/{source_id}', json={**source_payload, 'revision': 1, 'enabled': False}, headers=admin_csrf).status_code == 200

        from cryptography.fernet import Fernet
        from app.api.v1.routes import model_connections
        from app.models import ModelConnection
        key_cipher = Fernet(Fernet.generate_key())
        monkeypatch.setattr(model_connections, 'cipher', lambda: key_cipher)
        connection_payload = {"name": "测试连接", "base_url": "https://example.com/v1", "model_name": "test-model", "api_key": "test-secret", "enabled": False}
        assert creator.get('/api/v1/model-connections').status_code == 403
        assert admin.post('/api/v1/model-connections', json=connection_payload).status_code == 403
        assert admin.post('/api/v1/model-connections', json={**connection_payload, 'base_url': 'http://example.com'}, headers=admin_csrf).status_code == 422
        connection = admin.post('/api/v1/model-connections', json=connection_payload, headers=admin_csrf)
        assert connection.status_code == 201
        assert 'api_key' not in connection.json() and 'encrypted_key' not in connection.json()
        connection_id = connection.json()['id']
        with Session(engine) as db:
            stored = db.get(ModelConnection, connection_id).encrypted_key
            assert stored != 'test-secret'
            assert key_cipher.decrypt(stored.encode()) == b'test-secret'
        updated = admin.put(f'/api/v1/model-connections/{connection_id}', json={**connection_payload, 'api_key': '', 'enabled': True}, headers=admin_csrf)
        assert updated.status_code == 200 and updated.json()['enabled'] is True
        with Session(engine) as db:
            assert db.get(ModelConnection, connection_id).encrypted_key == stored
        assert creator.put(f'/api/v1/model-connections/{connection_id}', json=connection_payload, headers=creator_csrf).status_code == 403
        assert creator.get('/api/v1/agent-configs/writer').status_code == 403
        config = {'prompt': '产品：{{product}}', 'primary_model_id': connection_id, 'variables': {}}
        validation = admin.post('/api/v1/agent-configs/writer/validate', json=config, headers=admin_csrf)
        assert validation.status_code == 200 and not validation.json()['valid']
        config['variables'] = {'product': '耳机'}
        validation = admin.post('/api/v1/agent-configs/writer/validate', json=config, headers=admin_csrf)
        assert validation.json()['valid'] and validation.json()['preview'] == '产品：耳机'
        saved = admin.post('/api/v1/agent-configs/writer', json={'base_version': 0, 'configuration': config}, headers=admin_csrf)
        assert saved.status_code == 201 and saved.json()['version'] == 1
        assert admin.post('/api/v1/agent-configs/writer', json={'base_version': 0, 'configuration': config}, headers=admin_csrf).status_code == 409
        assert admin.post('/api/v1/agent-configs/writer', json={'base_version': 1, 'configuration': {**config, 'max_iterations': 999}}, headers=admin_csrf).status_code == 422
        assert admin.post('/api/v1/agent-configs/writer', json={'base_version': 1, 'configuration': {**config, 'allowed_tools': ['delete_everything']}}, headers=admin_csrf).status_code == 422
        saved = admin.post('/api/v1/agent-configs/writer', json={'base_version': 1, 'configuration': {**config, 'prompt': '新版'}}, headers=admin_csrf)
        assert saved.status_code == 201
        history = admin.get('/api/v1/agent-configs/writer').json()
        assert len(history) == 2 and history[1]['configuration']['prompt'] == '产品：{{product}}'
        from app.api.v1.routes import agent_configs
        monkeypatch.setattr(agent_configs, 'cipher', lambda: key_cipher)
        calls = []
        def fake_complete(*args):
            calls.append(args)
            return {'text': '收到', 'usage': {'prompt_tokens': 20, 'completion_tokens': 5}}
        monkeypatch.setattr(agent_configs.model_gateway, 'complete', fake_complete)
        vid = history[0]['id']
        assert admin.post(f'/api/v1/agent-configs/writer/{vid}/publish', json={'expected_active_id': None}, headers=admin_csrf).status_code == 409
        assert admin.post(f'/api/v1/agent-configs/writer/{vid}/test', headers=admin_csrf).status_code == 409
        assert not calls
        assert admin.put('/api/v1/budget', json={'daily_limit': 10, 'currency': 'CNY'}, headers=admin_csrf).status_code == 200
        priced = {**connection_payload, 'enabled': True, 'options': {'input_price': 1, 'output_price': 2, 'currency': 'CNY', 'capability': 'text'}}
        assert admin.put(f'/api/v1/model-connections/{connection_id}', json=priced, headers=admin_csrf).status_code == 200
        version = admin.post('/api/v1/agent-configs/writer', json={'base_version': 2, 'configuration': {**config, 'budget': 1}}, headers=admin_csrf).json()
        vid = version['id']
        assert admin.post(f'/api/v1/agent-configs/writer/{vid}/test', headers=admin_csrf).status_code == 200
        assert len(calls) == 1
        assert admin.get('/api/v1/budget/usage').json()[0]['status'] == 'settled'
        assert admin.post(f'/api/v1/agent-configs/writer/{vid}/publish', json={'expected_active_id': None}, headers=admin_csrf).status_code == 200
        assert admin.post(f'/api/v1/agent-configs/writer/{vid}/publish', json={'expected_active_id': None}, headers=admin_csrf).status_code == 409
        assert admin.put(f'/api/v1/model-connections/{connection_id}', json={**priced, 'model_name': 'changed-model'}, headers=admin_csrf).status_code == 200
        assert admin.post(f'/api/v1/agent-configs/writer/{vid}/publish', json={'expected_active_id': vid}, headers=admin_csrf).status_code == 409
        assert creator.put('/api/v1/budget', json={'daily_limit': 10}, headers=creator_csrf).status_code == 403
        rotated = admin.put(f'/api/v1/model-connections/{connection_id}', json={**connection_payload, 'api_key': 'replacement-secret'}, headers=admin_csrf)
        assert rotated.status_code == 200
        with Session(engine) as db:
            assert key_cipher.decrypt(db.get(ModelConnection, connection_id).encrypted_key.encode()) == b'replacement-secret'
            foreign_connection = ModelConnection(tenant_id='another-company', name='private', base_url='https://example.com', model_name='private', encrypted_key='private')
            db.add(foreign_connection)
            db.commit()
            foreign_id = foreign_connection.id
        assert len(admin.get('/api/v1/model-connections').json()) == 1
        assert admin.put(f'/api/v1/model-connections/{foreign_id}', json=connection_payload, headers=admin_csrf).status_code == 404
        skill_payload = {'skill_key': 'product-story', 'base_version': 0, 'manifest': {'name': '产品叙事', 'description': '种草写法', 'agents': ['writer'], 'industries': ['3C'], 'variables': []}, 'content': '使用{{tone}}语气，产品事实必须有依据。'}
        skill = admin.post('/api/v1/skills', json=skill_payload, headers=admin_csrf)
        assert skill.status_code == 201
        assert admin.post(f"/api/v1/skills/{skill.json()['id']}/publish", headers=admin_csrf).status_code == 422
        skill_payload['base_version'] = 1
        skill_payload['manifest']['variables'] = ['tone']
        skill = admin.post('/api/v1/skills', json=skill_payload, headers=admin_csrf).json()
        assert admin.post(f"/api/v1/skills/{skill['id']}/publish", headers=admin_csrf).status_code == 200
        assert creator.get('/api/v1/skills').status_code == 403
        binding = {'name': '伪造名称', 'version': '999', 'content': '试图替换正文', 'source_version_id': skill['id']}
        bound = admin.post('/api/v1/agent-configs/writer', json={'base_version': 3, 'configuration': {**config, 'skills': [binding], 'variables': {'product': '耳机', 'tone': '客观'}}}, headers=admin_csrf)
        assert bound.status_code == 201 and bound.json()['configuration']['skills'][0]['content'] == skill['content']
        assert admin.post('/api/v1/agent-configs/analyst', json={'base_version': 0, 'configuration': {**config, 'skills': [binding]}}, headers=admin_csrf).status_code == 422
        preview = admin.post(f"/api/v1/skills/{skill['id']}/preview", json={'tone': '客观'})
        assert preview.status_code == 200 and '客观' in preview.json()['preview']
        from app.api.v1.routes import mcp_servers
        monkeypatch.setattr(mcp_servers, 'cipher', lambda: key_cipher)
        mcp_payload = {'name': '测试工具服务', 'endpoint': 'https://example.com/mcp', 'token': 'private-mcp-token', 'enabled': True}
        assert creator.post('/api/v1/mcp-servers', json=mcp_payload, headers=creator_csrf).status_code == 403
        server = admin.post('/api/v1/mcp-servers', json=mcp_payload, headers=admin_csrf)
        assert server.status_code == 201
        assert 'private-mcp-token' not in server.text and 'encrypted_token' not in server.text
        server_id = server.json()['id']
        monkeypatch.setattr(mcp_servers.mcp_gateway, 'discover', lambda *args: [{'name': 'search', 'description': '只读查询', 'inputSchema': {'type': 'object'}}])
        discovered = admin.post(f'/api/v1/mcp-servers/{server_id}/discover', headers=admin_csrf)
        assert discovered.status_code == 200 and discovered.json()['tested_revision'] == 1
        edited = admin.put(f'/api/v1/mcp-servers/{server_id}', json={**mcp_payload, 'revision': 1, 'token': '', 'clear_token': True}, headers=admin_csrf)
        assert edited.status_code == 200 and not edited.json()['has_token'] and edited.json()['tested_revision'] is None and edited.json()['tools'] == []
        assert admin.put(f'/api/v1/mcp-servers/{server_id}', json={**mcp_payload, 'revision': 1}, headers=admin_csrf).status_code == 409

        product = admin.post("/api/v1/products", json={"sku": "EAR-001", "name": "开放式耳机", "category": "耳机", "group_id": group_id}, headers=admin_csrf)
        assert product.status_code == 201
        product_id = product.json()["id"]
        update_payload = {'name': '开放式耳机新版', 'category': '耳机', 'description': '已核实：蓝牙耳机', 'status': 'active',
                          'expected_name': '开放式耳机', 'expected_category': '耳机', 'expected_description': '', 'expected_status': 'draft'}
        assert creator.put(f'/api/v1/products/{product_id}', json=update_payload, headers=creator_csrf).status_code == 403
        assert admin.put(f'/api/v1/products/{product_id}', json=update_payload, headers=admin_csrf).status_code == 200
        assert admin.put(f'/api/v1/products/{product_id}', json=update_payload, headers=admin_csrf).status_code == 409
        assert len(admin.get('/api/v1/products?q=新版&product_status=active').json()) == 1
        assert creator.get('/api/v1/products?q=新版').json() == []
        from io import BytesIO
        from PIL import Image
        from app.api.v1.routes import product_assets
        from app.api.v1.routes import workflow_assets
        objects = {}
        class FakeStorage:
            def create_bucket(self, **kwargs): pass
            def put_object(self, **kwargs): objects[kwargs['Key']] = kwargs['Body']
            def get_object(self, **kwargs): return {'Body': BytesIO(objects[kwargs['Key']])}
            def delete_object(self, **kwargs): objects.pop(kwargs['Key'], None)
        monkeypatch.setattr(product_assets, 'storage', lambda: FakeStorage())
        monkeypatch.setattr(workflow_assets, 'storage', lambda: FakeStorage())
        image_bytes = BytesIO()
        Image.new('RGB', (20, 20)).save(image_bytes, format='PNG')
        assert admin.post(f'/api/v1/products/{product_id}/images', content=b'invalid', headers=admin_csrf).status_code == 400
        image_result = admin.post(f'/api/v1/products/{product_id}/images', content=image_bytes.getvalue(), headers=admin_csrf)
        assert image_result.status_code == 200
        image_url = f"/api/v1/products/{product_id}/images/{image_result.json()['id']}"
        assert admin.get(image_url).status_code == 200
        assert creator.get(image_url).status_code == 404
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
        assert creator.get(image_url).status_code == 200
        hotspot = creator.post("/api/v1/hotspots", json={"title": "耳机种草内容", "content_type": "article"}, headers=creator_csrf)
        assert hotspot.status_code == 201
        workflow = creator.post("/api/v1/workflows", json={"hotspot_id": hotspot.json()["id"]}, headers=creator_csrf)
        assert workflow.status_code == 201
        assert len(creator.get(f"/api/v1/workflows/{workflow.json()['id']}/events").json()) == 1
        assert creator.post(f"/api/v1/workflows/{workflow.json()['id']}/run", headers=creator_csrf).status_code == 503

        wid = workflow.json()['id']
        assert creator.get(f'/api/v1/workflows/{wid}/workspace').json()['revision'] == 0
        material_payload = {'revision': 0, 'material': '这是一篇用户有权使用的耳机种草参考文章，包含真实的产品使用场景。', 'rights_confirmed': True}
        assert creator.put(f'/api/v1/workflows/{wid}/material', json={**material_payload, 'rights_confirmed': False}, headers=creator_csrf).status_code == 422
        assert creator.put(f'/api/v1/workflows/{wid}/material', json=material_payload, headers=creator_csrf).status_code == 200
        assert creator.put(f'/api/v1/workflows/{wid}/material', json=material_payload, headers=creator_csrf).status_code == 409
        assert admin.put(f'/api/v1/model-connections/{connection_id}', json=priced, headers=admin_csrf).status_code == 200
        embedding_model = admin.post('/api/v1/model-connections', json={**priced, 'name': '嵌入模型', 'model_name': 'embed-test', 'options': {'capability': 'embedding', 'input_price': 1, 'output_price': 0, 'currency': 'CNY'}}, headers=admin_csrf)
        assert embedding_model.status_code == 201
        embedding_id = embedding_model.json()['id']
        assert admin.put('/api/v1/recommendation-settings', json={'embedding_connection_id': embedding_id, 'per_call_budget': 1}, headers=admin_csrf).status_code == 200
        from app.services import recommendations as recommendation_service
        monkeypatch.setattr(recommendation_service, 'cipher', lambda: key_cipher)
        embedding_calls = []
        def fake_embed(*args):
            embedding_calls.append(args)
            return {'embedding': [1.0, 0.0, 0.0], 'usage': {'prompt_tokens': 10, 'completion_tokens': 0}}
        monkeypatch.setattr(recommendation_service.model_gateway, 'embed', fake_embed)
        assert admin.post(f'/api/v1/products/{product_id}/embedding', headers=admin_csrf).json()['cached'] is False
        assert admin.post(f'/api/v1/products/{product_id}/embedding', headers=admin_csrf).json()['cached'] is True
        assert len(embedding_calls) == 1
        assert creator.post(f'/api/v1/products/{product_id}/embedding', headers=creator_csrf).status_code == 403
        recommendation_config = admin.post('/api/v1/agent-configs/recommender', json={'base_version': 0, 'configuration': {**config, 'budget': 1}}, headers=admin_csrf).json()
        recommendation_config_id = recommendation_config['id']
        assert admin.post(f'/api/v1/agent-configs/recommender/{recommendation_config_id}/test', headers=admin_csrf).status_code == 200
        assert admin.post(f'/api/v1/agent-configs/recommender/{recommendation_config_id}/publish', json={'expected_active_id': None}, headers=admin_csrf).status_code == 200
        from app.api.v1.routes import recommendations as recommendation_routes
        monkeypatch.setattr(recommendation_routes, 'cipher', lambda: key_cipher)
        import json
        monkeypatch.setattr(recommendation_service.model_gateway, 'complete', lambda *a: {'text': json.dumps({'products': [{'id': product_id, 'score': 70, 'reason': '耳机使用场景适配', 'evidence': '蓝牙耳机'}]}), 'usage': {'prompt_tokens': 10, 'completion_tokens': 10}})
        recommended = creator.post(f'/api/v1/workflows/{wid}/recommendations', json={'revision': 1, 'threshold': 65}, headers=creator_csrf)
        assert recommended.status_code == 200 and recommended.json()['items'][0]['product_id'] == product_id
        assert creator.post(f'/api/v1/workflows/{wid}/recommendations', json={'revision': 1, 'threshold': 0}, headers=creator_csrf).status_code == 422
        monkeypatch.setattr(recommendation_service.model_gateway, 'complete', fake_complete)
        assert creator.put(f'/api/v1/workflows/{wid}/product', json={'revision': 1, 'product_id': product_id}, headers=creator_csrf).status_code == 200
        assert creator.get(f'/api/v1/workflows/{wid}/workspace').json()['product_snapshot']['name'] == '开放式耳机新版'
        assert admin.put(f'/api/v1/model-connections/{connection_id}', json=priced, headers=admin_csrf).status_code == 200
        assert admin.post(f'/api/v1/agent-configs/writer/{vid}/test', headers=admin_csrf).status_code == 200
        run_headers = {**creator_csrf, 'Idempotency-Key': 'creation-request-1'}
        started = creator.post(f'/api/v1/workflows/{wid}/agent-runs', json={'revision': 2}, headers=run_headers)
        assert started.status_code == 202
        run_id = started.json()['id']
        assert 'snapshot' not in started.json()
        repeated = creator.post(f'/api/v1/workflows/{wid}/agent-runs', json={'revision': 2}, headers=run_headers)
        assert repeated.status_code == 202 and repeated.json()['id'] == run_id
        assert creator.post(f'/api/v1/workflows/{wid}/agent-runs', json={'revision': 2}, headers={**creator_csrf, 'Idempotency-Key': 'different-request-1'}).status_code == 409
        assert manager.get(f'/api/v1/agent-runs/{run_id}/events').status_code == 404
        assert creator.post(f'/api/v1/agent-runs/{run_id}/cancel', headers=creator_csrf).status_code == 200
        assert creator.post(f'/api/v1/agent-runs/{run_id}/cancel', headers=creator_csrf).status_code == 409
        from app.models import AgentRun
        with Session(engine) as db:
            db.get(AgentRun, run_id).status = 'failed'
            db.commit()
        streamed = creator.get(f'/api/v1/agent-runs/{run_id}/events/stream')
        assert streamed.status_code == 200 and 'id: 1' in streamed.text and 'finished' in streamed.text
        resumed = creator.get(f'/api/v1/agent-runs/{run_id}/events/stream', headers={'Last-Event-ID': '1'})
        assert 'id: 1' not in resumed.text
        audit_log = admin.get('/api/v1/audit-events')
        assert audit_log.status_code == 200 and len(audit_log.json()) > 0
        assert all(secret not in audit_log.text for secret in ['test-secret', 'private-mcp-token', 'replacement-secret'])
        assert creator.get('/api/v1/audit-events').status_code == 403
        draft_payload = {'revision': 2, 'title': '人工耳机文章', 'units': [{'id': 'p1', 'text': '第一段文字', 'image_description': '耳机使用场景'}, {'id': 'p2', 'text': '第二段保持不变', 'image_description': ''}]}
        first_draft = creator.post(f'/api/v1/workflows/{wid}/artifacts', json=draft_payload, headers=creator_csrf)
        assert first_draft.status_code == 201
        updated_units = [{**draft_payload['units'][0], 'text': '局部修改第一段'}, draft_payload['units'][1]]
        second_draft = creator.post(f'/api/v1/workflows/{wid}/artifacts', json={**draft_payload, 'revision': 3, 'units': updated_units}, headers=creator_csrf)
        assert second_draft.status_code == 201
        versions = creator.get(f'/api/v1/workflows/{wid}/artifacts').json()
        assert versions[1]['units'][0]['text'] == '第一段文字'
        assert versions[0]['units'][1] == versions[1]['units'][1]
        assert creator.post(f'/api/v1/workflows/{wid}/finalize', json={'revision': 4, 'artifact_id': first_draft.json()['id']}, headers=creator_csrf).status_code == 409
        assert creator.post(f'/api/v1/workflows/{wid}/finalize', json={'revision': 4, 'artifact_id': second_draft.json()['id']}, headers=creator_csrf).status_code == 409
        attached = creator.post(f"/api/v1/workflows/{wid}/artifacts/{second_draft.json()['id']}/units/p1/image?revision=4", content=image_bytes.getvalue(), headers=creator_csrf)
        assert attached.status_code == 201
        attached_artifact = attached.json()
        asset_id = attached_artifact['units'][0]['image_asset_id']
        asset_url = f'/api/v1/workflows/{wid}/assets/{asset_id}'
        assert creator.get(asset_url).status_code == 200
        assert manager.get(asset_url).status_code == 404
        assert creator.post(f'/api/v1/workflows/{wid}/finalize', json={'revision': 5, 'artifact_id': attached_artifact['id']}, headers=creator_csrf).status_code == 200
        assert len(creator.get('/api/v1/contents').json()) == 1
        download_url = f"/api/v1/contents/{attached_artifact['id']}/download"
        from zipfile import ZipFile
        package = creator.get(download_url)
        assert package.status_code == 200 and package.headers['content-type'] == 'application/zip'
        with ZipFile(BytesIO(package.content)) as archive:
            assert '未审核' in archive.read('content.md').decode()
            assert f'images/{asset_id}.jpg' in archive.namelist()
        assert creator.put(f'/api/v1/workflows/{wid}/material', json={**material_payload, 'revision': 5}, headers=creator_csrf).status_code == 409

        video = creator.post('/api/v1/hotspots', json={'title': '视频参考', 'content_type': 'video'}, headers=creator_csrf).json()
        video_workflow = creator.post('/api/v1/workflows', json={'hotspot_id': video['id']}, headers=creator_csrf).json()['id']
        assert creator.put(f'/api/v1/workflows/{video_workflow}/material', json=material_payload, headers=creator_csrf).status_code == 200
        assert creator.put(f'/api/v1/workflows/{video_workflow}/product', json={'revision': 1, 'product_id': product_id}, headers=creator_csrf).status_code == 200
        script = creator.post(f'/api/v1/workflows/{video_workflow}/artifacts', json={**draft_payload, 'title': '已确认剧本'}, headers=creator_csrf)
        assert script.status_code == 201 and script.json()['kind'] == 'script'
        assert creator.post(f'/api/v1/workflows/{video_workflow}/finalize', json={'revision': 3, 'artifact_id': script.json()['id']}, headers=creator_csrf).status_code == 200
        assert creator.get(f'/api/v1/workflows/{video_workflow}/workspace').json()['step'] == 'storyboarding'
        assert creator.get(f"/api/v1/contents/{script.json()['id']}/download").status_code == 409
        invalid_storyboard = creator.post(f'/api/v1/workflows/{video_workflow}/artifacts', json={**draft_payload, 'revision': 4}, headers=creator_csrf)
        assert invalid_storyboard.status_code == 422
        shots = [{'id': 'shot1', 'text': '产品展示', 'image_description': '桌面上的耳机', 'shot_size': '特写', 'camera_movement': '缓慢推进', 'composition': '居中', 'duration_seconds': 30}]
        storyboard = creator.post(f'/api/v1/workflows/{video_workflow}/artifacts', json={'revision': 4, 'title': '分镜稿', 'units': shots}, headers=creator_csrf)
        assert storyboard.status_code == 201 and storyboard.json()['kind'] == 'storyboard'
        assert creator.post(f'/api/v1/workflows/{video_workflow}/finalize', json={'revision': 5, 'artifact_id': storyboard.json()['id']}, headers=creator_csrf).status_code == 200
        assert len(creator.get('/api/v1/contents').json()) == 3
        assert '运镜：缓慢推进' in creator.get(f"/api/v1/contents/{storyboard.json()['id']}/download").text
        entry_payload = {'title': '聊天入口素材', 'material': '这是从聊天入口直接提交的完整参考文章素材，已确认可以用于本次创作。', 'content_type': 'text', 'rights_confirmed': True}
        entry_headers = {**creator_csrf, 'Idempotency-Key': 'workflow-entry-test'}
        entry = creator.post('/api/v1/workflow-entry', json=entry_payload, headers=entry_headers)
        assert entry.status_code == 201 and entry.json()['current_step'] == 'drafting'
        duplicate = creator.post('/api/v1/workflow-entry', json=entry_payload, headers=entry_headers)
        assert duplicate.status_code == 201 and duplicate.json()['id'] == entry.json()['id']
        assert creator.post('/api/v1/workflow-entry', json={**entry_payload, 'title': '不同内容'}, headers=entry_headers).status_code == 409
        assert manager.post('/api/v1/workflow-entry', json=entry_payload, headers={**manager_csrf, 'Idempotency-Key': 'forbidden-entry-test'}).status_code == 403

        assert admin.delete(f"/api/v1/product-groups/{group_id}/grants/{user_id}", headers=admin_csrf).status_code == 200
        assert creator.get("/api/v1/products").json() == []
        assert creator.get(image_url).status_code == 404
        assert creator.get(download_url).status_code == 403
        assert creator.get(asset_url).status_code == 403
        assert creator.get(f'/api/v1/agent-runs/{run_id}/events').status_code == 403
        assert creator.get('/api/v1/contents').json() == []
        assert admin.delete(image_url, headers=admin_csrf).status_code == 200
        assert all(not key.endswith(image_result.json()['id']) for key in objects)
        assert admin.patch(f"/api/v1/users/{user_id}/active", json={"is_active": False}, headers=admin_csrf).status_code == 200
        assert creator.get("/api/v1/auth/me").status_code == 401
        assert admin.post("/api/v1/auth/change-password", json={"current_password": "wrong", "new_password": "NewPassword123!"}, headers=admin_csrf).status_code == 400
        assert admin.post("/api/v1/auth/change-password", json={"current_password": "AdminPassword123!", "new_password": "NewPassword123!"}, headers=admin_csrf).status_code == 200
        assert admin.get("/api/v1/auth/me").status_code == 401
        assert admin.post("/api/v1/auth/login", json={"username": "admin", "password": "NewPassword123!"}).status_code == 200
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
