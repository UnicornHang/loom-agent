import hashlib
import json
import math
import re
from fastapi import HTTPException
from sqlalchemy import select, cast, Text, bindparam
from sqlalchemy.types import UserDefinedType
from app.models import Product, ProductEmbedding, ModelConnection, RecommendationPolicy
from app.services.product_access import visible_products
from app.services.model_budget import reserve, settle
from app.services.model_secrets import cipher
from app.services import model_gateway

def product_text(product):
    return f'{product.name}\n{product.sku}\n{product.category}\n{product.description}'

def source_hash(product): return hashlib.sha256(product_text(product).encode()).hexdigest()
def model_hash(model): return hashlib.sha256((model.base_url + '\n' + model.model_name).encode()).hexdigest()

def connection(db, user):
    policy = db.get(RecommendationPolicy, user.tenant_id)
    model = db.get(ModelConnection, policy.embedding_connection_id) if policy and policy.embedding_connection_id else None
    if not model or model.tenant_id != user.tenant_id or not model.enabled or model.options.get('capability') != 'embedding': raise HTTPException(409, '请先配置启用的嵌入模型')
    return policy, model

def embedding_call(db, user, model, text, budget):
    messages = [{'role': 'user', 'content': text}]
    reservation = reserve(db, user.tenant_id, model, messages, 0, budget)
    db.commit()
    try: result = model_gateway.embed(model.base_url, cipher().decrypt(model.encrypted_key.encode()).decode(), model.model_name, text)
    except Exception:
        reservation.status = 'uncertain'; db.commit()
        raise HTTPException(502, '嵌入模型调用失败；预留额度保留待核对') from None
    settle(reservation, result['usage'], model.options); db.commit()
    return result['embedding']

def tokens(text):
    values = set(re.findall(r'[a-z0-9]+', text.lower()))
    for phrase in re.findall(r'[\u4e00-\u9fff]+', text):
        values.update(phrase[i:i + 2] for i in range(max(1, len(phrase) - 1)))
    return values

def lexical_score(query, product):
    q = tokens(query); p = tokens(product_text(product))
    return len(q & p) / max(1, min(len(q), len(p)))

class Vector(UserDefinedType):
    cache_ok = True
    def get_col_spec(self, **kw): return 'vector'

def retrieve(db, user, model, query, vector):
    # The permission predicate is part of the SQL query before similarity results leave the DB.
    ids = visible_products(user).with_only_columns(Product.id).where(Product.status == 'active')
    query_statement = select(Product, ProductEmbedding).join(ProductEmbedding, ProductEmbedding.product_id == Product.id).where(
        Product.id.in_(ids), ProductEmbedding.connection_id == model.id, ProductEmbedding.model_hash == model_hash(model), ProductEmbedding.dimensions == len(vector))
    if db.bind.dialect.name == 'postgresql':
        distance = cast(cast(ProductEmbedding.embedding, Text), Vector()).op('<=>')(cast(bindparam('query_vector', json.dumps(vector)), Vector()))
        rows = db.execute(query_statement.add_columns(distance)).all()
    else:
        rows = [(product, embedding, 1 - sum(a * b for a, b in zip(vector, embedding.embedding))) for product, embedding in db.execute(query_statement)]
    candidates = []
    for product, embedding, distance in rows:
        if source_hash(product) != embedding.source_hash or distance is None or not math.isfinite(float(distance)): continue
        semantic = max(0, min(1, 1 - float(distance)))
        lexical = lexical_score(query, product)
        candidates.append({'product': product, 'semantic_score': round(semantic * 100, 2), 'keyword_score': round(lexical * 100, 2), 'retrieval_score': round((semantic * 0.7 + lexical * 0.3) * 100, 2)})
    return sorted(candidates, key=lambda c: (-c['retrieval_score'], c['product'].id))[:30]
