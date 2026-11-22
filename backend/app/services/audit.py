from app.models import AuditEvent

def record(db, user, action, object_id, summary):
    """Only caller-authored summaries; never serialize request bodies or credentials."""
    db.add(AuditEvent(tenant_id=user.tenant_id, user_id=user.id, action=action, object_id=object_id, summary=summary))
