from alembic import op
import sqlalchemy as sa

revision = '0006_model_execution'
down_revision = '0005_workspaces'
branch_labels = depends_on = None

def upgrade():
    op.add_column('model_connections', sa.Column('options', sa.JSON(), nullable=False, server_default='{}'))
    op.create_table('budget_policies', sa.Column('tenant_id', sa.String(32), primary_key=True), sa.Column('daily_limit_micros', sa.Integer(), nullable=False), sa.Column('currency', sa.String(3), nullable=False))
    op.create_table('usage_reservations', sa.Column('id', sa.String(32), primary_key=True), sa.Column('tenant_id', sa.String(32), nullable=False), sa.Column('day', sa.String(10), nullable=False), sa.Column('amount_micros', sa.Integer(), nullable=False), sa.Column('status', sa.String(20), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_usage_reservations_tenant_id', 'usage_reservations', ['tenant_id'])
    op.create_table('configuration_tests', sa.Column('id', sa.String(32), primary_key=True), sa.Column('configuration_id', sa.String(32), sa.ForeignKey('agent_configurations.id'), nullable=False), sa.Column('fingerprint', sa.String(64), nullable=False), sa.Column('succeeded', sa.Boolean(), nullable=False), sa.Column('summary', sa.Text(), nullable=False), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_configuration_tests_configuration_id', 'configuration_tests', ['configuration_id'])

def downgrade():
    op.drop_table('configuration_tests')
    op.drop_table('usage_reservations')
    op.drop_table('budget_policies')
    op.drop_column('model_connections', 'options')
