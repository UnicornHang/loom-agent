from alembic import op
import sqlalchemy as sa

revision = '0015_recommendations'
down_revision = '0014_workflow_entry'
branch_labels = depends_on = None

def upgrade():
    op.create_table('recommendation_policies', sa.Column('tenant_id', sa.String(32), primary_key=True), sa.Column('embedding_connection_id', sa.String(32), sa.ForeignKey('model_connections.id'), nullable=True), sa.Column('per_call_budget', sa.Integer(), nullable=False))
    op.create_table('product_embeddings', sa.Column('id', sa.String(64), primary_key=True), sa.Column('product_id', sa.String(32), sa.ForeignKey('products.id'), nullable=False), sa.Column('connection_id', sa.String(32), sa.ForeignKey('model_connections.id'), nullable=False), sa.Column('source_hash', sa.String(64), nullable=False), sa.Column('model_hash', sa.String(64), nullable=False), sa.Column('dimensions', sa.Integer(), nullable=False), sa.Column('embedding', sa.JSON(), nullable=False))
    op.create_index('ix_product_embeddings_product_id', 'product_embeddings', ['product_id'])

def downgrade():
    op.drop_table('product_embeddings')
    op.drop_table('recommendation_policies')
