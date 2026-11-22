from alembic import op
import sqlalchemy as sa

revision = '0010_skills'
down_revision = '0009_sources'
branch_labels = depends_on = None

def upgrade():
    op.create_table('skill_versions', sa.Column('id', sa.String(32), primary_key=True), sa.Column('tenant_id', sa.String(32), nullable=False), sa.Column('skill_key', sa.String(100), nullable=False), sa.Column('version', sa.Integer(), nullable=False), sa.Column('status', sa.String(20), nullable=False), sa.Column('manifest', sa.JSON(), nullable=False), sa.Column('content', sa.Text(), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint('tenant_id', 'skill_key', 'version', name='uq_skill_version'))
    op.create_index('ix_skill_versions_tenant_id', 'skill_versions', ['tenant_id'])

def downgrade():
    op.drop_table('skill_versions')
