from alembic import op
import sqlalchemy as sa

revision = "0004_agent_configuration"
down_revision = "0003_model_connections"
branch_labels = depends_on = None

def upgrade():
    op.create_table("agent_configurations",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("tenant_id", sa.String(32), nullable=False),
        sa.Column("agent_type", sa.String(40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "agent_type", "version", name="uq_agent_configuration_version"))
    op.create_index("ix_agent_configurations_tenant_id", "agent_configurations", ["tenant_id"])

def downgrade():
    op.drop_table("agent_configurations")
