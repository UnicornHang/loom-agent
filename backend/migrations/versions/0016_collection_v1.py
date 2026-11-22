from alembic import op
import sqlalchemy as sa

revision = '0016_collection_v1'
down_revision = '0015_recommendations'
branch_labels = depends_on = None

def upgrade():
    with op.batch_alter_table('collection_runs') as batch:
        batch.add_column(sa.Column('snapshot', sa.JSON(), nullable=False, server_default='{}'))
        batch.add_column(sa.Column('counts', sa.JSON(), nullable=False, server_default='{}'))
        batch.add_column(sa.Column('dispatched', sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table('hotspots') as batch:
        batch.add_column(sa.Column('source_item_id', sa.String(100), nullable=True))
        batch.add_column(sa.Column('source_metrics', sa.JSON(), nullable=False, server_default='{}'))
        batch.add_column(sa.Column('collected_at', sa.DateTime(timezone=True), nullable=True))
        batch.create_unique_constraint('uq_hotspot_source_item', ['tenant_id', 'source_kind', 'source_item_id'])

def downgrade():
    with op.batch_alter_table('hotspots') as batch:
        batch.drop_constraint('uq_hotspot_source_item', type_='unique')
        batch.drop_column('collected_at'); batch.drop_column('source_metrics'); batch.drop_column('source_item_id')
    with op.batch_alter_table('collection_runs') as batch:
        batch.drop_column('dispatched'); batch.drop_column('counts'); batch.drop_column('snapshot')
