# Build phase — PRISM-Cache v0.1

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Optional Redis backend:

```bash
pip install -e ".[redis]"
docker compose up -d redis
export REDIS_URL=redis://localhost:6379/0
```

## Quick usage

```python
from prism_cache import PrismPipeline
from prism_cache.pipeline import PrismConfig
from prism_cache.models import ChunkResult

pipeline = PrismPipeline(PrismConfig(org_id="acme", corpus_id="handbook"))

def my_retriever(query, *, top_k, filters):
    # call Qdrant / etc. only on cache miss
    return [ChunkResult("chunk-1", 0.95)]

chunks, tier0, ctx, lookup = pipeline.rag_retrieve(
    "what is the expense policy?",
    my_retriever,
    user_id="user-123",
    top_k=5,
)
```

## Examples

```bash
python examples/rag_demo.py
python examples/tier3_load_test.py --users 50 --queries 5
```

## Tests

```bash
pytest
```

## Redis store

```python
from prism_cache.tier3 import RedisRetrievalStore, Tier3RetrievalCache

store = RedisRetrievalStore("redis://localhost:6379/0")
cache = Tier3RetrievalCache(store, embed_model_id="text-embedding-3-small")
```

## Corpus invalidation

When documents update, bump version (new keys miss stale entries):

```python
pipeline.invalidate_corpus()
```

Wire `InMemoryCorpusVersionProvider` to your CMS webhook in production.
