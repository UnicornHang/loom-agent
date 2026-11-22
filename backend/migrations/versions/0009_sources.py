from alembic import op
import sqlalchemy as sa

revision = '0009_sources'
down_revision = '0008_reviews'
branch_labels = depends_on = None

def upgrade():
    op.create_table('source_configurations', sa.Column('id', sa.String(32), primary_key=True), sa.Column('tenant_id', sa.String(32), nullable=False), sa.Column('revision', sa.Integer(), nullable=False), sa.Column('name', sa.String(100), nullable=False), sa.Column('adapter', sa.String(40), nullable=False), sa.Column('industry', sa.String(100), nullable=False), sa.Column('keywords', sa.JSON(), nullable=False), sa.Column('interval_minutes', sa.Integer(), nullable=False), sa.Column('enabled', sa.Boolean(), nullable=False), sa.Column('authorization_note', sa.Text(), nullable=False), sa.Column('next_run_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_source_configurations_tenant_id', 'source_configurations', ['tenant_id'])
    op.create_table('collection_runs', sa.Column('id', sa.String(32), primary_key=True), sa.Column('source_id', sa.String(32), sa.ForeignKey('source_configurations.id'), nullable=False), sa.Column('source_revision', sa.Integer(), nullable=False), sa.Column('trigger', sa.String(20), nullable=False), sa.Column('status', sa.String(30), nullable=False), sa.Column('summary', sa.Text(), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_collection_runs_source_id', 'collection_runs', ['source_id'])

def downgrade():
    op.drop_table('collection_runs')
    op.drop_table('source_configurations')
