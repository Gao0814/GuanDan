"""Knowledge-base loading interfaces for phase-1."""

from dataclasses import dataclass, field
from pathlib import Path


_RULE_REL_PATH = Path("rule_corpus/guandan_rules.md")
_EXP_REL_PATH = Path("experience_corpus/basic_human_experience.md")


@dataclass(frozen=True, slots=True)
class KnowledgeDocument:
    """A knowledge entry loaded from local markdown corpus."""

    doc_id: str
    layer: str
    content: str
    source_path: str
    metadata: dict[str, str] = field(default_factory=dict)


class KnowledgeBaseLoader:
    """Loader skeleton for rule and experience corpora."""

    def __init__(self, rag_root: Path) -> None:
        self._rag_root = rag_root

    @property
    def rag_root(self) -> Path:
        return self._rag_root

    def _load_file_documents(self, *, layer: str, rel_path: Path, prefix: str) -> tuple[KnowledgeDocument, ...]:
        source_file = (self._rag_root / rel_path).resolve()
        if not source_file.exists():
            raise FileNotFoundError(f"knowledge file not found: {source_file}")

        lines = source_file.read_text(encoding="utf-8").splitlines()
        docs: list[KnowledgeDocument] = []
        for idx, raw in enumerate(lines, start=1):
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#"):
                continue

            doc_id = f"{prefix}:{idx}"
            docs.append(
                KnowledgeDocument(
                    doc_id=doc_id,
                    layer=layer,
                    content=line,
                    source_path=f"rag/{rel_path.as_posix()}",
                    metadata={"line": str(idx)},
                )
            )
        return tuple(docs)

    def load_rule_documents(self) -> tuple[KnowledgeDocument, ...]:
        return self._load_file_documents(
            layer="rule",
            rel_path=_RULE_REL_PATH,
            prefix="rule",
        )

    def load_experience_documents(self) -> tuple[KnowledgeDocument, ...]:
        return self._load_file_documents(
            layer="experience",
            rel_path=_EXP_REL_PATH,
            prefix="exp",
        )

    def load_all_documents(self) -> tuple[KnowledgeDocument, ...]:
        return self.load_rule_documents() + self.load_experience_documents()
