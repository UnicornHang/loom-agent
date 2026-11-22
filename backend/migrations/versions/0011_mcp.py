from alembic import op
import sqlalchemy as sa

revision = '0011_mcp'
down_revision = '0010_skills'
branch_labels = depends_on = None

def upgrade():
    op.create_table('mcp_servers', sa.Column('id', sa.String(32), primary_key=True), sa.Column('tenant_id', sa.String(32), nullable=False), sa.Column('revision', sa.Integer(), nullable=False), sa.Column('name', sa.String(100), nullable=False), sa.Column('endpoint', sa.String(500), nullable=False), sa.Column('encrypted_token', sa.Text(), nullable=True), sa.Column('timeout_seconds', sa.Integer(), nullable=False), sa.Column('data_scope', sa.String(40), nullable=False), sa.Column('enabled', sa.Boolean(), nullable=False), sa.Column('tools', sa.JSON(), nullable=False), sa.Column('tested_revision', sa.Integer(), nullable=True))
    op.create_index('ix_mcp_servers_tenant_id', 'mcp_servers', ['tenant_id'])

def downgrade():
    op.drop_table('mcp_servers')
