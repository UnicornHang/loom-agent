from alembic import op
import sqlalchemy as sa

revision = '0007_agent_runs'
down_revision = '0006_model_execution'
branch_labels = depends_on = None

def upgrade():
    op.add_column('artifact_versions', sa.Column('workspace_revision', sa.Integer(), nullable=False, server_default='0'))
    op.create_table('agent_runs', sa.Column('id', sa.String(32), primary_key=True), sa.Column('workflow_id', sa.String(32), sa.ForeignKey('workflows.id'), nullable=False), sa.Column('request_key', sa.String(64), nullable=False), sa.Column('configuration_id', sa.String(32), sa.ForeignKey('agent_configurations.id'), nullable=False), sa.Column('workspace_revision', sa.Integer(), nullable=False), sa.Column('snapshot', sa.JSON(), nullable=False), sa.Column('status', sa.String(30), nullable=False), sa.Column('error', sa.Text(), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint('workflow_id', 'request_key', name='uq_run_request'))
    op.create_index('ix_agent_runs_workflow_id', 'agent_runs', ['workflow_id'])
    op.create_table('agent_run_events', sa.Column('id', sa.String(32), primary_key=True), sa.Column('run_id', sa.String(32), sa.ForeignKey('agent_runs.id'), nullable=False), sa.Column('sequence', sa.Integer(), nullable=False), sa.Column('kind', sa.String(40), nullable=False), sa.Column('summary', sa.Text(), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint('run_id', 'sequence', name='uq_run_event_sequence'))
    op.create_index('ix_agent_run_events_run_id', 'agent_run_events', ['run_id'])
    op.create_table('outbox_tasks', sa.Column('id', sa.String(32), primary_key=True), sa.Column('run_id', sa.String(32), sa.ForeignKey('agent_runs.id'), unique=True, nullable=False), sa.Column('sent', sa.Boolean(), nullable=False))

def downgrade():
    op.drop_table('outbox_tasks')
    op.drop_table('agent_run_events')
    op.drop_table('agent_runs')
    op.drop_column('artifact_versions', 'workspace_revision')
