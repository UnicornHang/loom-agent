import hashlib
from sqlalchemy import select, func

def tenant_lock(db, tenant_id, scope):
    """Serialize tenant configuration transitions, including rows not created yet."""
    if db.bind.dialect.name == 'postgresql':
        key = int.from_bytes(hashlib.sha256(f'{scope}:{tenant_id}'.encode()).digest()[:8], 'big', signed=True)
        db.execute(select(func.pg_advisory_xact_lock(key)))
