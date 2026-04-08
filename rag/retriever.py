"""Knowledge retrieval interface skeleton for phase-1."""

from dataclasses import dataclass, field
import re

from rag.kb_loader import KnowledgeDocument


_ALLOWED_SOURCES = {
    "rag/rule_corpus/guandan_rules.md",
    "rag/experience_corpus/basic_human_experience.md",
}


def _normalize(text: str) -> str:
    return text.strip().lower()


def _tokenize_ascii(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9_]+", _normalize(text)))


def _score(query: str, content: str) -> float:
    q = _normalize(query)
    c = _normalize(content)
    if not q:
        return 0.0

    score = 0.0
    if q in c:
        score += 5.0

    q_tokens = _tokenize_ascii(q)
    c_tokens = _tokenize_ascii(c)
    score += float(len(q_tokens & c_tokens))

    # Basic CJK overlap for simple Chinese keyword matching.
    cjk_chars = [ch for ch in q if "\u4e00" <= ch <= "\u9fff"]
    if cjk_chars:
        overlap = sum(1 for ch in cjk_chars if ch in c)
        score += overlap * 0.2
    return score


@dataclass(frozen=True, slots=True)
class RetrievalResult:
    """A retriever hit with traceable source and explanation."""

    doc_id: str
    layer: str
    snippet: str
    score: float
    source_path: str
    metadata: dict[str, str] = field(default_factory=dict)


class KnowledgeRetriever:
    """Retriever abstraction over loaded knowledge documents."""

    def __init__(self, documents: tuple[KnowledgeDocument, ...]) -> None:
        for doc in documents:
            if doc.source_path not in _ALLOWED_SOURCES:
                raise ValueError(f"unsupported source path for retriever boundary: {doc.source_path}")
        self._documents = documents

    @property
    def documents(self) -> tuple[KnowledgeDocument, ...]:
        return self._documents

    def retrieve(self, query: str, layer: str, top_k: int = 3) -> tuple[RetrievalResult, ...]:
        if layer not in {"rule", "experience"}:
            raise ValueError("layer must be 'rule' or 'experience'")
        if top_k <= 0:
            return ()

        candidates: list[tuple[float, KnowledgeDocument]] = []
        for doc in self._documents:
            if doc.layer != layer:
                continue
            s = _score(query, doc.content)
            if s <= 0:
                continue
            candidates.append((s, doc))

        candidates.sort(key=lambda item: item[0], reverse=True)
        results: list[RetrievalResult] = []
        for score, doc in candidates[:top_k]:
            results.append(
                RetrievalResult(
                    doc_id=doc.doc_id,
                    layer=doc.layer,
                    snippet=doc.content,
                    score=score,
                    source_path=doc.source_path,
                    metadata=dict(doc.metadata),
                )
            )
        return tuple(results)
