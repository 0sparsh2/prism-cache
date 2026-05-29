from __future__ import annotations

from abc import ABC, abstractmethod


class CorpusVersionProvider(ABC):
    """Tie cache invalidation to document pipeline / CMS version."""

    @abstractmethod
    def current_version(self, org_id: str, corpus_id: str) -> str: ...

    @abstractmethod
    def bump(self, org_id: str, corpus_id: str) -> str: ...


class InMemoryCorpusVersionProvider(CorpusVersionProvider):
    def __init__(self, default_version: str = "1") -> None:
        self._versions: dict[tuple[str, str], str] = {}
        self._default = default_version

    def current_version(self, org_id: str, corpus_id: str) -> str:
        return self._versions.get((org_id, corpus_id), self._default)

    def bump(self, org_id: str, corpus_id: str) -> str:
        key = (org_id, corpus_id)
        current = int(self._versions.get(key, self._default))
        new = str(current + 1)
        self._versions[key] = new
        return new
