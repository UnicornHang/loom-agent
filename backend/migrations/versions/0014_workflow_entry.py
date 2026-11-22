from alembic import op
import sqlalchemy as sa

revision = '0014_workflow_entry'
down_revision = '0013_workflow_assets'
branch_labels = depends_on = None

def upgrade():
    with op.batch_alter_table('workflows') as batch:
        batch.add_column(sa.Column('entry_key', sa.String(64), nullable=True))
        batch.add_column(sa.Column('entry_hash', sa.String(64), nullable=True))
        batch.create_unique_constraint('uq_workflow_entry_key', ['tenant_id', 'created_by_user_id', 'entry_key'])

def downgrade():
    with op.batch_alter_table('workflows') as batch:
        batch.drop_constraint('uq_workflow_entry_key', type_='unique')
        batch.drop_column('entry_key')
        batch.drop_column('entry_hash')
