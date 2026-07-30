"""RAG advisor interface for agent-side knowledge support."""

from dataclasses import dataclass, field
import re

from agents.opening_strategy import normalize_hand_strength
from rag.kb_loader import KnowledgeDocument
from rag.retriever import KnowledgeRetriever


_OUT_OF_SCOPE_KEYWORDS = (
    # Not part of the single-game mainline.
    "进贡",
    "还贡",
    "升级",
    "多局",
    "比赛",
    "长局",
    "MCTS",
    "自博弈",
    "强化学习",
    "概率建模",
    "风格识别",
    # Unsupported pattern in current engine scope.
    "飞机",
)
_PRESSURE_PATTERNS = {"bomb", "straight_flush", "joker_bomb"}
_MAX_HIT_CHARS = 240
_TAG_WEIGHTS = {
    "scene": (40.0, 6.0),
    "action_context": (25.0, 4.0),
    "hand_strength": (15.0, 3.0),
    "phase": (10.0, 2.0),
}
_PRIORITY_WEIGHTS = {"high": 1.5, "medium": 0.75, "low": 0.25}


@dataclass(frozen=True, slots=True)
class RAGEvidence:
    """Knowledge snippet returned by RAG support modules."""

    source_id: str
    layer: str
    snippet: str
    metadata: dict[str, str] = field(default_factory=dict)


class RAGAdvisor:
    """Fetch rule/experience context without changing legal action truth."""

    def __init__(self, retriever: KnowledgeRetriever) -> None:
        self._retriever = retriever

    @staticmethod
    def _mark_conflict(snippet: str) -> tuple[str, str]:
        haystack = snippet.lower()
        for token in _OUT_OF_SCOPE_KEYWORDS:
            if token.lower() in haystack:
                return "rejected_conflict", f"contains_out_of_scope_token:{token}"
        return "accepted", ""

    @staticmethod
    def _coerce_int(value: object, default: int = 0) -> int:
        try:
            return int(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _clip(text: str, max_chars: int = _MAX_HIT_CHARS) -> str:
        value = text.strip()
        if len(value) <= max_chars:
            return value
        return value[: max_chars - 1].rstrip() + "…"

    @staticmethod
    def _is_pass(action: dict[str, object]) -> bool:
        return str(action.get("declared_pattern", "")) == "pass"

    @staticmethod
    def _metadata_values(metadata: dict[str, str], key: str) -> set[str]:
        raw = metadata.get(key, "")
        return {part.strip() for part in raw.split(",") if part.strip()}

    @staticmethod
    def _ascii_tokens(text: str) -> set[str]:
        return set(re.findall(r"[a-z0-9_]+", text.lower()))

    @staticmethod
    def _cjk_terms(text: str) -> set[str]:
        return {token for token in re.split(r"[\s,，:：;；/、\[\]()（）]+", text) if token}

    @staticmethod
    def _scene_tags(
        observation: dict[str, object],
        legal_actions: list[dict[str, object]],
        hand_eval: dict[str, object] | None = None,
    ) -> dict[str, object]:
        my_info = dict(observation.get("my_info", {}))
        current_round = dict(observation.get("current_round", {}))
        history = dict(observation.get("history", {}))

        hand_count = RAGAdvisor._coerce_int(my_info.get("hand_count"), default=-1)
        step_no = RAGAdvisor._coerce_int(current_round.get("step_no"), default=-1)
        constraint = str(current_round.get("constraint", "unknown"))
        table_action = current_round.get("table_action")
        current_level_rank = str(current_round.get("current_level_rank", ""))

        other_players = list(observation.get("other_players", []))
        other_counts = [
            RAGAdvisor._coerce_int(dict(player).get("hand_count"), default=-1)
            for player in other_players
            if not bool(dict(player).get("finished", False))
        ]
        finish_order = list(dict(history).get("finish_order", []))

        if hand_count > 0 and (hand_count < 10 or any(0 < count < 6 for count in other_counts) or finish_order):
            phase = "endgame"
        elif step_no == 0:
            phase = "opening"
        elif step_no >= 0:
            phase = "midgame"
        else:
            phase = "unknown"

        if phase == "endgame":
            scene = "endgame"
        elif table_action is None and constraint == "free":
            scene = "lead_opening" if phase == "opening" else "lead"
        elif table_action is not None or constraint != "free":
            scene = "follow_response"
        else:
            scene = "unknown"

        hand_cards = [str(card) for card in my_info.get("hand_cards", [])]
        wildcard_token = f"{current_level_rank}H" if current_level_rank else ""
        has_hand_wildcard = bool(wildcard_token and wildcard_token in hand_cards)
        has_action_wildcard = any(
            RAGAdvisor._coerce_int(action.get("wildcard_count"), default=0) > 0
            for action in legal_actions
        )
        has_joker_control = any(card in {"SJ", "BJ"} for card in hand_cards)
        has_bomb = any(str(action.get("declared_pattern", "")) in _PRESSURE_PATTERNS for action in legal_actions)
        can_play_out_all = any(
            not RAGAdvisor._is_pass(action)
            and hand_count > 0
            and len(list(action.get("carrier_cards", []))) == hand_count
            for action in legal_actions
        )
        can_bomb_response = scene == "follow_response" and has_bomb

        if isinstance(hand_eval, dict):
            hand_strength = normalize_hand_strength(hand_eval)
        else:
            hand_strength = "unknown"

        if scene in {"lead_opening", "lead"}:
            action_context = "free_lead"
        elif scene == "follow_response":
            action_context = "follow"
        elif scene == "endgame":
            action_context = "endgame"
        else:
            action_context = "unknown"

        return {
            "scene": scene,
            "phase": phase,
            "hand_strength": hand_strength,
            "action_context": action_context,
            "has_bomb": has_bomb,
            "has_wildcard": has_hand_wildcard or has_action_wildcard,
            "has_joker_control": has_joker_control,
            "can_play_out_all": can_play_out_all,
            "can_bomb_response": can_bomb_response,
            "wildcard_action_present": has_action_wildcard,
        }

    @staticmethod
    def _topics_from_scene_tags(scene_tags: dict[str, object]) -> set[str]:
        topics: set[str] = set()
        scene = str(scene_tags.get("scene", "unknown"))
        phase = str(scene_tags.get("phase", "unknown"))
        if scene in {"lead_opening", "lead"}:
            topics.update({"opening", "control", "run_out"})
        if scene == "follow_response":
            topics.update({"follow_response", "pass", "opponent_pressure"})
        if scene == "endgame" or phase == "endgame" or bool(scene_tags.get("can_play_out_all")):
            topics.update({"endgame", "run_out"})
        if bool(scene_tags.get("has_bomb")) or bool(scene_tags.get("can_bomb_response")):
            topics.update({"bomb", "straight_flush", "joker_bomb", "control"})
        if bool(scene_tags.get("has_wildcard")) or bool(scene_tags.get("wildcard_action_present")):
            topics.add("wildcard")
        if bool(scene_tags.get("has_joker_control")):
            topics.update({"joker", "joker_bomb", "control"})
        return topics

    @staticmethod
    def build_query(scene_tags: dict[str, object]) -> str:
        parts = [f"{key}:{value}" for key, value in scene_tags.items()]
        zh_terms = ["掼蛋", "单局", "当前规则", "合法动作", "经验"]
        if scene_tags.get("scene") in {"lead_opening", "lead"}:
            zh_terms.extend(["首出", "开局", "自由出牌"])
        if scene_tags.get("scene") == "follow_response":
            zh_terms.extend(["跟牌", "压制", "pass", "炸弹", "同花顺", "天王炸"])
        if scene_tags.get("phase") == "endgame":
            zh_terms.extend(["终局", "少牌", "阻断", "出完"])
        if scene_tags.get("has_wildcard"):
            zh_terms.append("逢人配")
        if scene_tags.get("has_joker_control"):
            zh_terms.append("王")
        if scene_tags.get("can_bomb_response"):
            zh_terms.append("跨型压制")
        return " ".join(parts + zh_terms)

    @staticmethod
    def _tag_match_score(doc_values: set[str], wanted: str, exact_weight: float, any_weight: float) -> float | None:
        if not doc_values:
            return None
        if wanted and wanted != "unknown" and wanted in doc_values:
            return exact_weight
        if "any" in doc_values:
            return any_weight
        if wanted == "unknown" and "unknown" in doc_values:
            return any_weight
        return None

    @staticmethod
    def _keyword_score(doc: KnowledgeDocument, query: str, desired_topics: set[str]) -> float:
        score = 0.0
        metadata = dict(doc.metadata)
        doc_topics = RAGAdvisor._metadata_values(metadata, "topic")
        topic_overlap = desired_topics & doc_topics
        score += len(topic_overlap) * 3.0
        if "any" in doc_topics:
            score += 0.5

        keywords = RAGAdvisor._metadata_values(metadata, "keywords_cn")
        query_terms = RAGAdvisor._cjk_terms(query)
        score += len(keywords & query_terms) * 1.0
        for keyword in keywords:
            if keyword and keyword in query:
                score += 0.4
            if keyword and keyword in doc.content:
                score += 0.1

        query_ascii = RAGAdvisor._ascii_tokens(query)
        metadata_ascii = RAGAdvisor._ascii_tokens(" ".join(metadata.values()))
        score += len(query_ascii & metadata_ascii) * 0.4

        priority = metadata.get("priority", "medium")
        score += _PRIORITY_WEIGHTS.get(priority, 0.0)
        return score

    @classmethod
    def _tag_score_document(
        cls,
        doc: KnowledgeDocument,
        *,
        scene_tags: dict[str, object],
        query: str,
        desired_topics: set[str],
    ) -> tuple[float, str, str] | None:
        combined_text = f"{doc.content} {' '.join(doc.metadata.values())}"
        status, reason = cls._mark_conflict(combined_text)
        if status != "accepted":
            return None

        score = 0.0
        for key, (exact_weight, any_weight) in _TAG_WEIGHTS.items():
            wanted = str(scene_tags.get(key, "unknown"))
            tag_score = cls._tag_match_score(
                cls._metadata_values(doc.metadata, key),
                wanted,
                exact_weight,
                any_weight,
            )
            if tag_score is None:
                return None
            score += tag_score

        score += cls._keyword_score(doc, query, desired_topics)
        if score <= 0:
            return None
        return score, status, reason

    def _retrieve_tagged(
        self,
        *,
        layer: str,
        scene_tags: dict[str, object],
        query: str,
        top_k: int,
    ) -> tuple[RAGEvidence, ...]:
        if top_k <= 0:
            return ()

        desired_topics = self._topics_from_scene_tags(scene_tags)
        candidates: list[tuple[float, int, KnowledgeDocument]] = []
        for idx, doc in enumerate(self._retriever.documents):
            if doc.layer != layer:
                continue
            scored = self._tag_score_document(
                doc,
                scene_tags=scene_tags,
                query=query,
                desired_topics=desired_topics,
            )
            if scored is None:
                continue
            score, _, _ = scored
            candidates.append((score, idx, doc))

        candidates.sort(key=lambda item: (-item[0], item[1]))

        evidence: list[RAGEvidence] = []
        for score, _, doc in candidates[:top_k]:
            metadata = dict(doc.metadata)
            metadata.update(
                {
                    "source_path": doc.source_path,
                    "status": "accepted",
                    "score": f"{score:.2f}",
                }
            )
            evidence.append(
                RAGEvidence(
                    source_id=doc.doc_id,
                    layer=doc.layer,
                    snippet=doc.content,
                    metadata=metadata,
                )
            )
        return tuple(evidence)

    @staticmethod
    def _pack(evidence: RAGEvidence) -> dict[str, object]:
        return {
            "source_id": evidence.source_id,
            "layer": evidence.layer,
            "snippet": RAGAdvisor._clip(evidence.snippet),
            "metadata": dict(evidence.metadata),
        }

    @staticmethod
    def _accepted(evidence: tuple[RAGEvidence, ...]) -> list[dict[str, object]]:
        return [
            RAGAdvisor._pack(item)
            for item in evidence
            if item.metadata.get("status") == "accepted"
        ]

    def retrieve_rule_evidence(self, query: str, top_k: int = 3) -> tuple[RAGEvidence, ...]:
        hits = self._retriever.retrieve(query=query, layer="rule", top_k=top_k)
        evidence: list[RAGEvidence] = []
        for hit in hits:
            status, reason = self._mark_conflict(f"{hit.snippet} {' '.join(hit.metadata.values())}")
            metadata = {
                "source_path": hit.source_path,
                "status": status,
            }
            metadata.update(hit.metadata)
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
            status, reason = self._mark_conflict(f"{hit.snippet} {' '.join(hit.metadata.values())}")
            metadata = {
                "source_path": hit.source_path,
                "status": status,
            }
            metadata.update(hit.metadata)
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

    def get_rag_context(
        self,
        *,
        observation: dict[str, object],
        legal_actions: list[dict[str, object]],
        hand_eval: dict[str, object] | None = None,
        top_k: int = 3,
    ) -> dict[str, object]:
        scene_tags = self._scene_tags(observation, legal_actions, hand_eval)
        query = self.build_query(scene_tags)

        try:
            rule_evidence = self._retrieve_tagged(
                layer="rule",
                scene_tags=scene_tags,
                query=query,
                top_k=top_k,
            )
        except Exception:
            rule_evidence = ()

        try:
            experience_evidence = self._retrieve_tagged(
                layer="experience",
                scene_tags=scene_tags,
                query=query,
                top_k=top_k,
            )
        except Exception:
            experience_evidence = ()

        return {
            "scene_tags": scene_tags,
            "rule_hits": self._accepted(rule_evidence),
            "experience_hits": self._accepted(experience_evidence),
            "query": query,
        }
