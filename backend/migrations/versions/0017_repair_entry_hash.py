"""Repair development databases upgraded before entry_hash joined migration 0014."""
from alembic import op
import sqlalchemy as sa

revision = '0017_repair_entry_hash'
down_revision = '0016_collection_v1'
branch_labels = depends_on = None


def upgrade():
    columns = {column['name'] for column in sa.inspect(op.get_bind()).get_columns('workflows')}
    if 'entry_hash' not in columns:
        op.add_column('workflows', sa.Column('entry_hash', sa.String(64), nullable=True))


def downgrade():
    # 0014 already owns this column; keep it when returning to 0016.
    pass
