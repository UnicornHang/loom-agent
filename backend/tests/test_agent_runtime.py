import json
from cryptography.fernet import Fernet
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db import Base
from app.models import User, Hotspot, Workflow, WorkflowWorkspace, ModelConnection, AgentConfiguration, AgentRun, BudgetPolicy, ArtifactVersion, RunEvent, ReviewResult
from app.agents import runtime
from app.api.v1.routes.agent_configs import Configuration
import pytest

def test_local_rewrite_rejects_unrelated_changes():
    base = {'title': '原稿', 'units': [{'id': 'p1', 'text': '第一段', 'image_description': ''}, {'id': 'p2', 'text': '第二段', 'image_description': ''}]}
    draft = {'title': '原稿', 'style': '局部修改', 'units': [{**base['units'][0], 'text': '修改后的第一段'}, base['units'][1]]}
    assert runtime.parse_drafts(json.dumps({'drafts': [draft]}), 'article', base, 'p1')[0]['units'][1]['text'] == base['units'][1]['text']
    draft['units'] = [draft['units'][0], {**base['units'][1], 'text': '不允许修改第二段'}]
    with pytest.raises(ValueError, match='非目标段落'): runtime.parse_drafts(json.dumps({'drafts': [draft]}), 'article', base, 'p1')

def test_generation_requires_article_length_and_script_duration():
    short = [{'title': '短稿', 'style': str(i), 'units': [{'id': 'p1', 'text': '字数不足', 'image_description': ''}]} for i in range(3)]
    with pytest.raises(ValueError, match='800'): runtime.parse_drafts(json.dumps({'drafts': short}), 'article')
    with pytest.raises(ValueError, match='30'): runtime.parse_drafts(json.dumps({'drafts': short[:1]}), 'script')

def test_graph_produces_candidates_once_and_waits_for_human(monkeypatch):
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    sessions = sessionmaker(engine, expire_on_commit=False)
    encryption = Fernet(Fernet.generate_key())
    monkeypatch.setattr(runtime, 'cipher', lambda: encryption)
    with sessions() as db:
        user = User(username='creator', role='creator', password_hash='unused')
        hotspot = Hotspot(title='参考', content_type='text', summary='参考资料')
        db.add_all([user, hotspot]); db.flush()
        workflow = Workflow(hotspot_id=hotspot.id, created_by_user_id=user.id, current_step='drafting')
        model = ModelConnection(tenant_id='demo', name='test', base_url='https://example.com/v1', model_name='test', enabled=True, encrypted_key=encryption.encrypt(b'key').decode(), options={'input_price': 1, 'output_price': 2, 'currency': 'CNY'})
        db.add_all([workflow, model]); db.flush()
        config = Configuration(primary_model_id=model.id, prompt='请创作', budget=1, max_iterations=2, max_tokens=4096,
            skills=[{'name': '3C方法', 'version': '1', 'content': '3C_METHOD', 'industries': ['3C']}, {'name': '服装方法', 'version': '1', 'content': 'CLOTHING_METHOD', 'industries': ['服装']}]).model_dump()
        configuration = AgentConfiguration(tenant_id='demo', agent_type='writer', version=1, configuration=config, status='published')
        db.add(configuration); db.flush()
        db.add(WorkflowWorkspace(workflow_id=workflow.id, revision=1, rights_confirmed=True, material='用户确认有权使用的参考文章正文'))
        db.add(BudgetPolicy(tenant_id='demo', daily_limit_micros=10_000_000, currency='CNY'))
        run = AgentRun(workflow_id=workflow.id, request_key='test-key', configuration_id=configuration.id, workspace_revision=1, snapshot={
            'configuration': config, 'connections': [{'id': model.id, 'model_name': model.model_name, 'base_url': model.base_url, 'encrypted_key': model.encrypted_key, 'options': model.options}],
            'user_id': user.id, 'tenant_id': 'demo', 'industry': '3C', 'kind': 'article', 'material': '参考正文', 'product': None})
        db.add(run); db.commit(); run_id = run.id; workflow_id = workflow.id
    calls = []
    drafts = {'drafts': [{'title': f'候选{i}', 'style': style, 'units': [{'id': 'p1', 'text': '这是经过核实的耳机使用场景与体验描述。' * 45, 'image_description': ''}]} for i, style in enumerate(['测评', '故事', '清单'])]}
    def complete(*args):
        calls.append(args)
        return {'text': json.dumps(drafts if len(calls) == 1 else {'valid': True, 'issues': []}, ensure_ascii=False), 'usage': {'prompt_tokens': 30, 'completion_tokens': 20}}
    monkeypatch.setattr(runtime.model_gateway, 'complete', complete)
    saver = InMemorySaver()
    runtime.execute(run_id, sessions, saver)
    assert '3C_METHOD' in calls[0][3][0]['content'] and 'CLOTHING_METHOD' not in calls[0][3][0]['content']
    with sessions() as db:
        assert db.get(AgentRun, run_id).status == 'completed'
        artifacts = db.scalars(select(ArtifactVersion)).all()
        assert len(artifacts) == 3 and all(a.origin == 'agent' and a.status == 'draft' for a in artifacts)
        assert len({a.workspace_revision for a in artifacts}) == 1
        assert db.get(Workflow, workflow_id).current_step == 'drafting'
        assert db.scalars(select(RunEvent).where(RunEvent.kind == 'needs_confirmation')).first()
    runtime.execute(run_id, sessions, saver)
    assert len(calls) == 2
    assert saver.get({'configurable': {'thread_id': run_id}}) is not None
    with sessions() as db:
        original = db.get(AgentRun, run_id)
        artifact = db.scalars(select(ArtifactVersion)).first()
        artifact_id = artifact.id
        review_snapshot = {**original.snapshot, 'edit_request': {'operation': 'review'}, 'base_artifact': {'id': artifact.id, 'content_hash': artifact.content_hash, 'title': artifact.title, 'units': artifact.units}}
        review_run = AgentRun(workflow_id=workflow_id, request_key='review-request', configuration_id=original.configuration_id, workspace_revision=2, snapshot=review_snapshot)
        db.add(review_run); db.commit(); review_run_id = review_run.id
    monkeypatch.setattr(runtime.model_gateway, 'complete', lambda *a: {'text': json.dumps({'passed': True, 'findings': []}), 'usage': {'prompt_tokens': 10, 'completion_tokens': 5}})
    runtime.execute(review_run_id, sessions, saver)
    from app.api.v1.routes.workspaces import review_state
    with sessions() as db:
        assert db.get(AgentRun, review_run_id).status == 'completed'
        result = db.scalars(select(ReviewResult)).first()
        assert result.passed and result.artifact_id == artifact_id
        assert review_state(db, db.get(ArtifactVersion, artifact_id))[0] == 'AI审核通过'
        # A new version cannot inherit the previous version's review, even if wording matches.
        old = db.get(ArtifactVersion, artifact_id)
        new = ArtifactVersion(workflow_id=workflow_id, version=4, title=old.title, units=old.units, content_hash=old.content_hash, kind='article')
        db.add(new); db.flush()
        assert review_state(db, new)[0] == '未审核'
        db.rollback()
    with sessions() as db:
        run = db.get(AgentRun, run_id); run.status = 'running'; db.commit()
    runtime.execute(run_id, sessions, saver)
    with sessions() as db: assert db.get(AgentRun, run_id).status == 'uncertain'
    assert len(calls) == 2
    with sessions() as db:
        original = db.get(AgentRun, run_id)
        db.get(User, original.snapshot['user_id']).is_active = False
        disabled_run = AgentRun(workflow_id=workflow_id, request_key='disabled-user', configuration_id=original.configuration_id, workspace_revision=2, snapshot=original.snapshot)
        db.add(disabled_run); db.commit(); disabled_run_id = disabled_run.id
    blocked_calls = []
    monkeypatch.setattr(runtime.model_gateway, 'complete', lambda *a: blocked_calls.append(a))
    runtime.execute(disabled_run_id, sessions, saver)
    with sessions() as db:
        assert db.get(AgentRun, disabled_run_id).status == 'failed'
    assert blocked_calls == []
    engine.dispose()
