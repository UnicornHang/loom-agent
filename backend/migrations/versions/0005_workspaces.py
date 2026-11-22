from alembic import op
import sqlalchemy as sa

revision = '0005_workspaces'
down_revision = '0004_agent_configuration'
branch_labels = depends_on = None

def upgrade():
    op.create_table('workflow_workspaces',
        sa.Column('workflow_id', sa.String(32), sa.ForeignKey('workflows.id'), primary_key=True),
        sa.Column('revision', sa.Integer(), nullable=False),
        sa.Column('material', sa.Text(), nullable=False),
        sa.Column('rights_confirmed', sa.Boolean(), nullable=False),
        sa.Column('product_id', sa.String(32), sa.ForeignKey('products.id'), nullable=True),
        sa.Column('product_snapshot', sa.JSON(), nullable=True))
    op.create_table('artifact_versions',
        sa.Column('id', sa.String(32), primary_key=True),
        sa.Column('workflow_id', sa.String(32), sa.ForeignKey('workflows.id'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(30), nullable=False),
        sa.Column('title', sa.String(300), nullable=False),
        sa.Column('units', sa.JSON(), nullable=False),
        sa.Column('content_hash', sa.String(64), nullable=False),
        sa.Column('origin', sa.String(30), nullable=False),
        sa.Column('status', sa.String(30), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('workflow_id', 'version', name='uq_artifact_workflow_version'))
    op.create_index('ix_artifact_versions_workflow_id', 'artifact_versions', ['workflow_id'])

def downgrade():
    op.drop_table('artifact_versions')
    op.drop_table('workflow_workspaces')
