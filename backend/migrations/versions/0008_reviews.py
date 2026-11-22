from alembic import op
import sqlalchemy as sa

revision = '0008_reviews'
down_revision = '0007_agent_runs'
branch_labels = depends_on = None

def upgrade():
    op.create_table('review_results', sa.Column('id', sa.String(32), primary_key=True), sa.Column('artifact_id', sa.String(32), sa.ForeignKey('artifact_versions.id'), nullable=False), sa.Column('run_id', sa.String(32), sa.ForeignKey('agent_runs.id'), unique=True, nullable=False), sa.Column('content_hash', sa.String(64), nullable=False), sa.Column('passed', sa.Boolean(), nullable=False), sa.Column('findings', sa.JSON(), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_review_results_artifact_id', 'review_results', ['artifact_id'])

def downgrade():
    op.drop_table('review_results')
