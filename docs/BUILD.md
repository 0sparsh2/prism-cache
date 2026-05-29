# Build phase — PRISM-Cache v0.4

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

## Tier 4 — prefix cache + Anthropic body

```python
bundle = pipeline.rag_prepare(
    "what is the expense policy?",
    my_retriever,
    lambda chunk_id: fetch_chunk_text(chunk_id),
    user_id="user-123",
    model_id="claude-sonnet-4-20250514",
)

# Send to Anthropic Messages API
# client.messages.create(**bundle.anthropic_body)

# After response, record prefix cache usage
pipeline.record_prefix_cache_usage(
    response.usage.model_dump(),
    model_id="claude-sonnet-4-20250514",
    prefix_fingerprint=bundle.prompt.prefix_fingerprint,
)
print(pipeline.prefix_cache_dashboard())
```

Run `python examples/tier4_rag_prompt.py` for a full walkthrough.

## Tier 1 — FAQ exact cache + routes (Phase D)

```python
from prism_cache import PrismPipeline, PrismConfig

pipeline = PrismPipeline(PrismConfig(org_id="acme"))

answer = pipeline.faq_answer(
    "how do I reset my password?",
    route_name="internal-faq-bot",  # org-static, Tier 1 on
    generate=lambda q: call_litellm(q),
    user_id="alice",
).text

# coding tools: user-private, Tier 1 off — no org-wide sharing
pipeline.faq_answer("fix my code", "coding-assistant", generate, user_id="u1")
```

```bash
python examples/tier1_faq_demo.py
python examples/tier2_faq_demo.py
python examples/load_routes_from_config.py
```

## Tier 2 — semantic FAQ cache (Phase E)

Tier 1 catches normalized exact matches. Tier 2 catches **paraphrases** on `internal-faq-bot`
(org-static lane, low sensitivity, threshold default 0.95):

```python
pipeline = PrismPipeline(PrismConfig(org_id="acme", tier2_similarity_threshold=0.95))

result = pipeline.faq_answer(
    "how do I reset my login password?",
    "internal-faq-bot",
    generate=call_litellm,
    user_id="bob",
)
if result.cache_tier == CacheTier.TIER2:
    print(f"semantic hit sim={result.tier2.similarity:.2f}")
```

Pass a production embedder via `tier2_embed=` (OpenAI, etc.). Default `hash_bag_embed` is for tests/dev only.

Run red-team paraphrase checks: `pytest tests/test_tier2_redteam.py`

```bash
python examples/tier1_faq_demo.py
python examples/load_routes_from_config.py
```

## LiteLLM gateway

See [`docs/GATEWAY.md`](GATEWAY.md). Quick start:

```bash
pip install litellm
litellm --config gateway/litellm.prism.yaml --port 4000
```

## Examples

```bash
python examples/rag_demo.py
python examples/tier4_rag_prompt.py
python examples/tier1_faq_demo.py
python examples/tier2_faq_demo.py
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
