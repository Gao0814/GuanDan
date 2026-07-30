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

    @staticmethod
    def _parse_meta_value(value: str) -> str:
        raw = value.strip()
        if raw.startswith("[") and raw.endswith("]"):
            inner = raw[1:-1].strip()
            if not inner:
                return ""
            return ",".join(item.strip().strip("\"'") for item in inner.split(",") if item.strip())
        return raw.strip("\"'")

    @classmethod
    def _parse_front_matter(cls, lines: list[str]) -> tuple[dict[str, str], int] | None:
        if not lines or lines[0].strip() != "---":
            return None

        metadata: dict[str, str] = {}
        for idx, raw in enumerate(lines[1:], start=1):
            line = raw.strip()
            if line == "---":
                return (metadata, idx + 1)
            if not line or ":" not in line:
                continue
            key, value = line.split(":", 1)
            metadata[key.strip()] = cls._parse_meta_value(value)
        return None

    def _load_front_matter_documents(self, *, layer: str, rel_path: Path, prefix: str, lines: list[str]) -> tuple[KnowledgeDocument, ...]:
        docs: list[KnowledgeDocument] = []
        index = 0
        block_no = 1

        while index < len(lines):
            if lines[index].strip() != "---":
                index += 1
                continue

            parsed = self._parse_front_matter(lines[index:])
            if parsed is None:
                index += 1
                continue

            metadata, body_start_offset = parsed
            body_start = index + body_start_offset
            body_end = body_start
            while body_end < len(lines) and lines[body_end].strip() != "---":
                body_end += 1

            body = "\n".join(line.rstrip() for line in lines[body_start:body_end]).strip()
            if body:
                doc_id = metadata.get("id") or f"{prefix}:{block_no}"
                doc_layer = metadata.get("corpus", layer)
                if doc_layer == layer:
                    metadata = dict(metadata)
                    metadata["line"] = str(index + 1)
                    docs.append(
                        KnowledgeDocument(
                            doc_id=doc_id,
                            layer=layer,
                            content=body,
                            source_path=f"rag/{rel_path.as_posix()}",
                            metadata=metadata,
                        )
                    )
                    block_no += 1
            index = body_end

        return tuple(docs)

    def _load_line_documents(self, *, layer: str, rel_path: Path, prefix: str, lines: list[str]) -> tuple[KnowledgeDocument, ...]:
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

    def _load_file_documents(self, *, layer: str, rel_path: Path, prefix: str) -> tuple[KnowledgeDocument, ...]:
        source_file = (self._rag_root / rel_path).resolve()
        if not source_file.exists():
            raise FileNotFoundError(f"knowledge file not found: {source_file}")

        lines = source_file.read_text(encoding="utf-8").splitlines()
        if any(line.strip() == "---" for line in lines):
            return self._load_front_matter_documents(
                layer=layer,
                rel_path=rel_path,
                prefix=prefix,
                lines=lines,
            )
        return self._load_line_documents(layer=layer, rel_path=rel_path, prefix=prefix, lines=lines)

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
