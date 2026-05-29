import json
from unittest.mock import MagicMock, patch

from prism_cache.litellm_client import LiteLLMClient


def test_chat_and_embed_parse_response():
    client = LiteLLMClient(
        base_url="http://localhost:4000",
        api_key="sk-test",
        chat_model="gemini-2.5-flash-lite",
        embed_model="gemini-embed",
    )

    chat_body = json.dumps(
        {
            "choices": [{"message": {"content": "Reset at portal.example.com"}}],
        }
    ).encode()
    embed_body = json.dumps(
        {"data": [{"embedding": [0.1, 0.2, 0.3]}]},
    ).encode()

    def fake_urlopen(req, timeout=120):
        url = req.full_url
        if url.endswith("/v1/chat/completions"):
            return MagicMock(read=lambda: chat_body, status=200, __enter__=lambda s: s, __exit__=lambda *a: None)
        if url.endswith("/v1/embeddings"):
            return MagicMock(read=lambda: embed_body, status=200, __enter__=lambda s: s, __exit__=lambda *a: None)
        raise AssertionError(url)

    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        assert client.chat("reset password?") == "Reset at portal.example.com"
        assert client.embed("reset password?") == (0.1, 0.2, 0.3)

    gen = client.make_generate_fn()
    emb = client.make_embed_fn()
    with patch("urllib.request.urlopen", side_effect=fake_urlopen):
        assert "portal" in gen("how to reset?")
        assert len(emb("how to reset?")) == 3
