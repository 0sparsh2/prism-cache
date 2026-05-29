from prism_cache.models import ChunkResult
from prism_cache.tier4 import assemble_rag_prompt


def _text(cid: str) -> str:
    return f"Body of {cid}"


def test_same_chunks_same_fingerprint_different_user_query():
    chunks = [ChunkResult("b-chunk", 0.9), ChunkResult("a-chunk", 0.8)]
    p1 = assemble_rag_prompt(
        system_prompt="You are helpful.",
        chunks=chunks,
        user_query="what is expense policy?",
        resolve_chunk_text=_text,
    )
    p2 = assemble_rag_prompt(
        system_prompt="You are helpful.",
        chunks=list(reversed(chunks)),
        user_query="explain expense rules please",
        resolve_chunk_text=_text,
    )
    assert p1.prefix_fingerprint == p2.prefix_fingerprint
    assert p1.sorted_chunk_ids == ("a-chunk", "b-chunk")
    assert p1.user_query != p2.user_query


def test_different_chunks_different_fingerprint():
    a = assemble_rag_prompt(
        system_prompt="sys",
        chunks=[ChunkResult("c1", 1.0)],
        user_query="q",
        resolve_chunk_text=_text,
    )
    b = assemble_rag_prompt(
        system_prompt="sys",
        chunks=[ChunkResult("c2", 1.0)],
        user_query="q",
        resolve_chunk_text=_text,
    )
    assert a.prefix_fingerprint != b.prefix_fingerprint


def test_anthropic_cache_control_on_context_not_query():
    assembled = assemble_rag_prompt(
        system_prompt="sys",
        chunks=[ChunkResult("c1", 1.0)],
        user_query="my question",
        resolve_chunk_text=_text,
    )
    content = assembled.anthropic_messages[0]["content"]
    assert content[0].get("cache_control") == {"type": "ephemeral"}
    assert "cache_control" not in content[1]
