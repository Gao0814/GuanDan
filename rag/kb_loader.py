"""Knowledge-base loading with an isolated experience-governance plane."""

from collections import Counter
from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Mapping


_RULE_REL_PATH = Path("rule_corpus/guandan_rules.md")
_EXP_REL_PATH = Path("experience_corpus/basic_human_experience.md")
_EXP_PROVENANCE_REL_PATH = Path("experience_provenance.json")

_EXPERIENCE_REQUIRED_METADATA = frozenset(
    {
        "id",
        "corpus",
        "scene",
        "phase",
        "hand_strength",
        "action_context",
        "topic",
        "priority",
        "keywords_cn",
    }
)
_EXPERIENCE_OPTIONAL_METADATA = frozenset(
    {
        "strategy_intent",
        "threat_source",
        "opponent_count_bucket",
        "teammate_count_bucket",
        "belief_confidence",
        "strategy_domain",
        "guidance_mode",
        "candidate_requirements",
    }
)
_PROVENANCE_REQUIRED_FIELDS = frozenset(
    {
        "entry_id",
        "source_tier",
        "claim_type",
        "author_or_institution",
        "title",
        "publication",
        "url_or_bibliography",
        "locator",
        "scope",
        "evidence_status",
    }
)
_SCOPE_REQUIRED_FIELDS = frozenset(
    {"game_scope", "player_count", "tribute", "level_rank", "scenes"}
)
_SOURCE_TIERS = frozenset({"A", "B", "C", "R", "project_boundary"})
_CLAIM_TYPES = frozenset(
    {"strategy", "project_boundary", "rule_reference", "publication_record", "system_design"}
)
_EVIDENCE_STATUSES = frozenset({"active", "candidate", "registry_only"})
_SCENES = frozenset({"any", "lead_opening", "lead", "follow_response", "endgame"})
_PHASES = frozenset({"any", "opening", "midgame", "endgame"})
_HAND_STRENGTHS = frozenset({"any", "strong", "medium", "weak"})
_ACTION_CONTEXTS = frozenset({"any", "free_lead", "follow", "endgame"})
_PRIORITIES = frozenset({"high", "medium", "low"})
_STRATEGY_DOMAINS = frozenset({
    "overall_priority", "opening_free_lead", "hand_structure",
    "control_return_resource", "follow_control", "teammate_coordination",
    "danger_opponent_block", "bomb_wildcard_management", "endgame_planning",
    "uncertainty_probe",
})
_GUIDANCE_MODES = frozenset({"source_principle", "soft_hypothesis"})
_CANDIDATE_REQUIREMENTS = frozenset({"bomb_or_wildcard", "natural_pair"})


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

    @staticmethod
    def _valid_scope(scope: object) -> bool:
        if not isinstance(scope, Mapping) or set(scope) != _SCOPE_REQUIRED_FIELDS:
            return False
        scenes = scope.get("scenes")
        return (
            scope.get("game_scope") == "single_game"
            and scope.get("player_count") == 4
            and scope.get("tribute") == "none"
            and scope.get("level_rank") in {"2", "any"}
            and isinstance(scenes, list)
            and bool(scenes)
            and all(type(scene) is str and scene in _SCENES for scene in scenes)
        )

    @classmethod
    def _valid_provenance_record(cls, record: object) -> bool:
        if not isinstance(record, Mapping) or set(record) != _PROVENANCE_REQUIRED_FIELDS:
            return False
        if any(
            type(record.get(field)) is not str or not str(record.get(field)).strip()
            for field in _PROVENANCE_REQUIRED_FIELDS - {"scope"}
        ):
            return False
        source_tier = record.get("source_tier")
        claim_type = record.get("claim_type")
        evidence_status = record.get("evidence_status")
        if (
            source_tier not in _SOURCE_TIERS
            or claim_type not in _CLAIM_TYPES
            or evidence_status not in _EVIDENCE_STATUSES
            or not cls._valid_scope(record.get("scope"))
        ):
            return False
        if evidence_status == "active":
            return (source_tier, claim_type) in {
                ("B", "strategy"),
                ("C", "strategy"),
                ("project_boundary", "project_boundary"),
            }
        if evidence_status == "candidate":
            return source_tier in {"B", "C"} and claim_type == "strategy"
        return claim_type in {"rule_reference", "publication_record", "system_design"}

    def _load_experience_provenance(self) -> dict[str, Mapping[str, object]]:
        registry_path = (self._rag_root / _EXP_PROVENANCE_REL_PATH).resolve()
        try:
            payload = json.loads(registry_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {}
        if (
            not isinstance(payload, dict)
            or payload.get("schema") != "guandan_experience_provenance"
            or payload.get("version") != 1
            or not isinstance(payload.get("records"), list)
        ):
            return {}

        records: dict[str, Mapping[str, object]] = {}
        invalid_ids: set[str] = set()
        for raw_record in payload["records"]:
            entry_id = raw_record.get("entry_id") if isinstance(raw_record, Mapping) else None
            if type(entry_id) is not str or not entry_id or entry_id in records:
                if type(entry_id) is str and entry_id:
                    invalid_ids.add(entry_id)
                continue
            if not self._valid_provenance_record(raw_record):
                invalid_ids.add(entry_id)
                continue
            records[entry_id] = raw_record
        for entry_id in invalid_ids:
            records.pop(entry_id, None)
        return records

    @staticmethod
    def _experience_document_is_active(
        doc: KnowledgeDocument,
        registry: Mapping[str, Mapping[str, object]],
    ) -> bool:
        metadata_keys = set(doc.metadata) - {"line"}
        if (
            metadata_keys - (_EXPERIENCE_REQUIRED_METADATA | _EXPERIENCE_OPTIONAL_METADATA)
            or not _EXPERIENCE_REQUIRED_METADATA.issubset(metadata_keys)
            or any(
                type(doc.metadata.get(key)) is not str
                or not doc.metadata.get(key, "").strip()
                for key in metadata_keys
            )
            or doc.metadata.get("id") != doc.doc_id
            or doc.metadata.get("corpus") != "experience"
        ):
            return False

        def values(key: str) -> set[str]:
            return {value.strip() for value in doc.metadata.get(key, "").split(",") if value.strip()}

        scenes = values("scene")
        phases = values("phase")
        strengths = values("hand_strength")
        action_contexts = values("action_context")
        if (
            not scenes
            or not scenes.issubset(_SCENES)
            or not phases
            or not phases.issubset(_PHASES)
            or not strengths
            or not strengths.issubset(_HAND_STRENGTHS)
            or not action_contexts
            or not action_contexts.issubset(_ACTION_CONTEXTS)
            or doc.metadata["priority"] not in _PRIORITIES
            or not values("topic")
            or not values("keywords_cn")
        ):
            return False
        if "strategy_domain" in doc.metadata and not values("strategy_domain").issubset(_STRATEGY_DOMAINS):
            return False
        guidance_modes = values("guidance_mode")
        if guidance_modes and not guidance_modes.issubset(_GUIDANCE_MODES):
            return False
        candidate_requirements = values("candidate_requirements")
        if (
            ("candidate_requirements" in doc.metadata and not candidate_requirements)
            or not candidate_requirements.issubset(_CANDIDATE_REQUIREMENTS)
        ):
            return False
        record = registry.get(doc.doc_id)
        if record is None or record.get("evidence_status") != "active":
            return False
        scope = record.get("scope")
        if not isinstance(scope, Mapping):
            return False
        registry_scenes = scope.get("scenes")
        doc_scenes = scenes
        if record.get("source_tier") == "C":
            # C-tier material is deliberately visible only as an explicitly
            # reversible soft hypothesis, never as a local-action convention.
            if guidance_modes != {"soft_hypothesis"}:
                return False
        elif guidance_modes and guidance_modes != {"source_principle"}:
            return False
        return (
            isinstance(registry_scenes, list)
            and bool(doc_scenes)
            and ("any" in registry_scenes or doc_scenes.issubset(set(registry_scenes)))
        )

    def load_rule_documents(self) -> tuple[KnowledgeDocument, ...]:
        return self._load_file_documents(
            layer="rule",
            rel_path=_RULE_REL_PATH,
            prefix="rule",
        )

    def load_experience_documents(self) -> tuple[KnowledgeDocument, ...]:
        registry = self._load_experience_provenance()
        if not registry:
            return ()
        documents = self._load_file_documents(
            layer="experience",
            rel_path=_EXP_REL_PATH,
            prefix="exp",
        )
        id_counts = Counter(doc.doc_id for doc in documents)
        return tuple(
            doc
            for doc in documents
            if id_counts[doc.doc_id] == 1
            and self._experience_document_is_active(doc, registry)
        )

    def load_all_documents(self) -> tuple[KnowledgeDocument, ...]:
        return self.load_rule_documents() + self.load_experience_documents()
