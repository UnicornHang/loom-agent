from alembic import op
import sqlalchemy as sa

revision = '0012_audit'
down_revision = '0011_mcp'
branch_labels = depends_on = None

def upgrade():
    op.create_table('audit_events', sa.Column('id', sa.String(32), primary_key=True), sa.Column('tenant_id', sa.String(32), nullable=False), sa.Column('user_id', sa.String(32), nullable=False), sa.Column('action', sa.String(100), nullable=False), sa.Column('object_id', sa.String(100), nullable=False), sa.Column('summary', sa.String(500), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_audit_events_tenant_id', 'audit_events', ['tenant_id'])

def downgrade():
    op.drop_table('audit_events')
