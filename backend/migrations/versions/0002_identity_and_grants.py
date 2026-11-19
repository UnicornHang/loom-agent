"""Identity, sessions and product group grants."""

from alembic import op
import sqlalchemy as sa

revision = "0002_identity_and_grants"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("users",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("tenant_id", sa.String(32), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(30), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "username", name="uq_user_tenant_username"))
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    op.create_table("login_sessions",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("csrf_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_login_sessions_user_id", "login_sessions", ["user_id"])

    op.create_table("product_groups",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("tenant_id", sa.String(32), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tenant_id", "name", name="uq_product_group_tenant_name"))
    op.create_index("ix_product_groups_tenant_id", "product_groups", ["tenant_id"])

    op.create_table("product_grants",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("user_id", sa.String(32), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("group_id", sa.String(32), sa.ForeignKey("product_groups.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "group_id", name="uq_product_grant_user_group"))
    op.create_index("ix_product_grants_user_id", "product_grants", ["user_id"])
    op.create_index("ix_product_grants_group_id", "product_grants", ["group_id"])

    with op.batch_alter_table("products") as batch:
        batch.add_column(sa.Column("group_id", sa.String(32), nullable=True))
        batch.create_foreign_key("fk_products_group_id", "product_groups", ["group_id"], ["id"])
        batch.create_index("ix_products_group_id", ["group_id"])
    with op.batch_alter_table("workflows") as batch:
        batch.add_column(sa.Column("created_by_user_id", sa.String(32), nullable=True))
        batch.create_foreign_key("fk_workflows_created_by_user_id", "users", ["created_by_user_id"], ["id"])
        batch.create_index("ix_workflows_created_by_user_id", ["created_by_user_id"])


def downgrade():
    with op.batch_alter_table("workflows") as batch:
        batch.drop_index("ix_workflows_created_by_user_id")
        batch.drop_constraint("fk_workflows_created_by_user_id", type_="foreignkey")
        batch.drop_column("created_by_user_id")
    with op.batch_alter_table("products") as batch:
        batch.drop_index("ix_products_group_id")
        batch.drop_constraint("fk_products_group_id", type_="foreignkey")
        batch.drop_column("group_id")
    op.drop_table("product_grants")
    op.drop_table("product_groups")
    op.drop_table("login_sessions")
    op.drop_table("users")
