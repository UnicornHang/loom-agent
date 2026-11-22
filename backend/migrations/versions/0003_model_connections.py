from alembic import op
import sqlalchemy as sa

revision = "0003_model_connections"
down_revision = "0002_identity_and_grants"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("model_connections",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("tenant_id", sa.String(32), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("model_name", sa.String(200), nullable=False),
        sa.Column("encrypted_key", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_model_connections_tenant_id", "model_connections", ["tenant_id"])


def downgrade():
    op.drop_table("model_connections")
