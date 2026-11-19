"""Original product, hotspot, workflow and event tables."""

from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("products",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("tenant_id", sa.String(32), nullable=False),
        sa.Column("sku", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "sku", name="uq_product_tenant_sku"))
    op.create_index("ix_products_tenant_id", "products", ["tenant_id"])

    op.create_table("hotspots",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("tenant_id", sa.String(32), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(20), nullable=False),
        sa.Column("source_url", sa.String(1000)),
        sa.Column("source_kind", sa.String(30), nullable=False),
        sa.Column("industry", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_hotspots_tenant_id", "hotspots", ["tenant_id"])

    op.create_table("workflows",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("tenant_id", sa.String(32), nullable=False),
        sa.Column("hotspot_id", sa.String(32), sa.ForeignKey("hotspots.id"), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("current_step", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_workflows_tenant_id", "workflows", ["tenant_id"])

    op.create_table("agent_events",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("workflow_id", sa.String(32), sa.ForeignKey("workflows.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("agent_type", sa.String(50), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workflow_id", "sequence", name="uq_event_workflow_sequence"))
    op.create_index("ix_agent_events_workflow_id", "agent_events", ["workflow_id"])


def downgrade():
    op.drop_table("agent_events")
    op.drop_table("workflows")
    op.drop_table("hotspots")
    op.drop_table("products")
