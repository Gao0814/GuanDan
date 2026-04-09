"""RAG advisor interface for agent-side knowledge support."""

from dataclasses import dataclass, field

from rag.retriever import KnowledgeRetriever


_OUT_OF_SCOPE_KEYWORDS = (
    "钢板",
    "飞机",
    "同花顺",
    "王炸",
    "天王炸",
    "逢人配",
    "进贡",
    "还贡",
    "升级",
    "胜负",
)


@dataclass(frozen=True, slots=True)
class RAGEvidence:
    """Knowledge snippet returned by RAG support modules."""

    source_id: str
    layer: str
    snippet: str
    metadata: dict[str, str] = field(default_factory=dict)


class RAGAdvisor:
    """Interface skeleton used by agents to fetch rule/experience context."""

    def __init__(self, retriever: KnowledgeRetriever) -> None:
        self._retriever = retriever

    @staticmethod
    def _mark_conflict(snippet: str) -> tuple[str, str]:
        for token in _OUT_OF_SCOPE_KEYWORDS:
            if token in snippet:
                return "rejected_conflict", f"contains_out_of_scope_token:{token}"
        return "accepted", ""

    def retrieve_rule_evidence(self, query: str, top_k: int = 3) -> tuple[RAGEvidence, ...]:
        hits = self._retriever.retrieve(query=query, layer="rule", top_k=top_k)
        evidence: list[RAGEvidence] = []
        for hit in hits:
            status, reason = self._mark_conflict(hit.snippet)
            metadata = {
                "source_path": hit.source_path,
                "status": status,
            }
            if reason:
                metadata["reason"] = reason
            evidence.append(
                RAGEvidence(
                    source_id=hit.doc_id,
                    layer=hit.layer,
                    snippet=hit.snippet,
                    metadata=metadata,
                )
            )
        return tuple(evidence)

    def retrieve_experience_evidence(self, query: str, top_k: int = 3) -> tuple[RAGEvidence, ...]:
        hits = self._retriever.retrieve(query=query, layer="experience", top_k=top_k)
        evidence: list[RAGEvidence] = []
        for hit in hits:
            status, reason = self._mark_conflict(hit.snippet)
            metadata = {
                "source_path": hit.source_path,
                "status": status,
            }
            if reason:
                metadata["reason"] = reason
            evidence.append(
                RAGEvidence(
                    source_id=hit.doc_id,
                    layer=hit.layer,
                    snippet=hit.snippet,
                    metadata=metadata,
                )
            )
        return tuple(evidence)
