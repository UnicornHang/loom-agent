from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db import Base
from app.models import User, ProductGroup, ProductGrant, Product, ModelConnection, ProductEmbedding
from app.services.recommendations import source_hash, model_hash, retrieve

def test_hybrid_retrieval_excludes_unauthorized_and_stale_products():
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user = User(username='creator', password_hash='unused', role='creator')
        allowed, forbidden = ProductGroup(name='已授权'), ProductGroup(name='未授权')
        model = ModelConnection(tenant_id='demo', name='embedding', base_url='https://example.com/v1', model_name='embedding', encrypted_key='unused', enabled=True)
        db.add_all([user, allowed, forbidden, model]); db.flush()
        db.add(ProductGrant(user_id=user.id, group_id=allowed.id))
        products = [Product(group_id=group.id, sku=str(i), name='耳机', category='耳机', description='适用于运动', status='active') for i, group in enumerate([allowed, forbidden])]
        db.add_all(products); db.flush()
        for i, product in enumerate(products):
            db.add(ProductEmbedding(id=str(i), product_id=product.id, connection_id=model.id, source_hash=source_hash(product), model_hash=model_hash(model), dimensions=3, embedding=[1, 0, 0]))
        db.commit()
        results = retrieve(db, user, model, '运动耳机种草', [1, 0, 0])
        assert len(results) == 1 and results[0]['product'].id == products[0].id
        products[0].description = '资料更新，旧索引应失效'
        db.commit()
        assert retrieve(db, user, model, '运动耳机种草', [1, 0, 0]) == []
    engine.dispose()
