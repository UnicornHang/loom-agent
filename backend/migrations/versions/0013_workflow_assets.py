from alembic import op
import sqlalchemy as sa

revision = '0013_workflow_assets'
down_revision = '0012_audit'
branch_labels = depends_on = None

def upgrade():
    op.create_table('workflow_assets', sa.Column('id', sa.String(32), primary_key=True), sa.Column('workflow_id', sa.String(32), sa.ForeignKey('workflows.id'), nullable=False), sa.Column('object_key', sa.String(300), nullable=False), sa.Column('content_hash', sa.String(64), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_workflow_assets_workflow_id', 'workflow_assets', ['workflow_id'])

def downgrade():
    op.drop_table('workflow_assets')
