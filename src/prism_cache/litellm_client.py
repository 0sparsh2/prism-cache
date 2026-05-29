from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from prism_cache.tier1 import GenerateFn
from prism_cache.tier2 import EmbedFn


def _retry_seconds_from_body(body: str) -> float | None:
    match = re.search(r"retry in (\d+(?:\.\d+)?)s", body, re.I)
    if match:
        return float(match.group(1))
    match = re.search(r'"retryDelay":\s*"(\d+)s"', body)
    if match:
        return float(match.group(1))
    return None


def _http_error_with_hint(exc: urllib.error.HTTPError, body: str) -> RuntimeError:
    if exc.code == 429 and (
        "quota" in body.lower() or "GenerateRequestsPerDay" in body
    ):
        return RuntimeError(
            "Gemini API quota exceeded (free tier is often ~20 generate requests/day "
            "for gemini-2.5-flash-lite). Options: wait for daily reset, enable billing "
            "on Google AI Studio, set PRISM_CHAT_MODEL=deepseek-v4-flash in .env for "
            "NIM chat, or run python examples/faq_litellm_gemini.py --dry-run"
        )
    return RuntimeError(f"LiteLLM HTTP {exc.code}: {body[:500]}")


@dataclass(frozen=True)
class LiteLLMClient:
    """
    OpenAI-compatible client for a local LiteLLM proxy.

    Used by PRISM Tier 2 (embeddings) and FAQ generate callbacks (chat).
    """

    base_url: str
    api_key: str
    chat_model: str
    embed_model: str
    timeout_seconds: int = 120

    @classmethod
    def from_env(cls) -> LiteLLMClient:
        # PRISM_CHAT_MODEL overrides GEMINI_MODEL (e.g. deepseek-v4-flash when Gemini quota is out)
        chat = os.environ.get("PRISM_CHAT_MODEL") or os.environ.get(
            "GEMINI_MODEL", "gemini-2.5-flash-lite"
        )
        return cls(
            base_url=os.environ.get("LITELLM_BASE_URL", "http://localhost:4000").rstrip(
                "/"
            ),
            api_key=os.environ["LITELLM_MASTER_KEY"],
            chat_model=chat,
            embed_model=os.environ.get("GEMINI_EMBED_MODEL", "gemini-embed"),
        )

    def _post(self, path: str, body: dict[str, Any], *, max_retries: int = 3) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        payload = json.dumps(body).encode()
        last_error: urllib.error.HTTPError | None = None

        for attempt in range(max_retries):
            req = urllib.request.Request(
                url,
                data=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    return json.load(resp)
            except urllib.error.HTTPError as exc:
                last_error = exc
                raw = exc.read().decode(errors="replace")
                if exc.code == 429 and attempt < max_retries - 1:
                    delay = _retry_seconds_from_body(raw) or (5 * (attempt + 1))
                    time.sleep(min(delay, 60))
                    continue
                raise _http_error_with_hint(exc, raw) from exc

        if last_error:
            raise last_error
        raise RuntimeError("unreachable")

    def chat(
        self,
        user_message: str,
        *,
        system: str | None = None,
        max_tokens: int = 256,
    ) -> str:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user_message})
        data = self._post(
            "/v1/chat/completions",
            {
                "model": self.chat_model,
                "messages": messages,
                "max_tokens": max_tokens,
            },
        )
        if "error" in data:
            raise RuntimeError(data["error"])
        return str(data["choices"][0]["message"]["content"]).strip()

    def embed(self, text: str) -> tuple[float, ...]:
        data = self._post(
            "/v1/embeddings",
            {"model": self.embed_model, "input": text},
        )
        if "error" in data:
            raise RuntimeError(data["error"])
        vector = data["data"][0]["embedding"]
        return tuple(float(x) for x in vector)

    def make_generate_fn(
        self,
        *,
        system: str | None = None,
        max_tokens: int = 256,
    ) -> GenerateFn:
        def _generate(query: str) -> str:
            return self.chat(query, system=system, max_tokens=max_tokens)

        return _generate

    def make_embed_fn(self) -> EmbedFn:
        return self.embed

    def health_check(self) -> bool:
        try:
            req = urllib.request.Request(
                f"{self.base_url}/v1/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                return resp.status == 200
        except (urllib.error.URLError, urllib.error.HTTPError):
            return False


def load_dotenv(path: str) -> None:
    """Minimal .env loader (no extra dependency)."""
    if not os.path.isfile(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)
