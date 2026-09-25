"""RAG advisor interface for agent-side knowledge support."""

from dataclasses import dataclass, field
import re

from agents.game_phase import GamePhaseContext, classify_game_phase, is_endgame_phase, phase_matches
from agents.opening_strategy import normalize_hand_strength
from agents.action_structure import summarize_candidate_contrasts, summarize_candidate_structures
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
_CANDIDATE_REQUIREMENTS = frozenset(
    {
        "bomb_or_wildcard",
        "natural_pair",
        "natural_pair_single",
        "natural_group_single",
        "natural_sequence_single",
        "bomb_strength_resource",
        "natural_single_cost",
        "straight_strength",
        "sequence_structure_loss",
        "triple_split_repartition",
        "straight_flush_bomb_fragment",
        "steel_plate_strength",
        "triple_pair_kicker_gradient",
        "single_control_resource",
        "wildcard_resource",
        "bomb_residual",
        "opening_natural_shape",
        "teammate_control_resource",
        "teammate_table_choice",
        "danger_block_resource",
        "danger_block_choice",
    }
)
_RELATION_SPECIFIC_SOFT_REQUIREMENTS = frozenset(
    {
        "natural_single_cost",
        "bomb_strength_resource",
        "bomb_residual",
        "triple_split_repartition",
        "straight_flush_bomb_fragment",
        "steel_plate_strength",
        "triple_pair_kicker_gradient",
    }
)
_KNOWLEDGE_METADATA_KEYS = frozenset(
    {
        "scene",
        "phase",
        "hand_strength",
        "action_context",
        "topic",
        "priority",
        "keywords_cn",
        "strategy_intent",
        "threat_source",
        "opponent_count_bucket",
        "teammate_count_bucket",
        "belief_confidence",
        "strategy_domain",
        "guidance_mode",
    }
)


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
    def _rank_from_public_token(token: object) -> str | None:
        if not isinstance(token, str):
            return None
        if token in {"SJ", "BJ"}:
            return token
        if len(token) < 2 or token[-1] not in {"S", "H", "C", "D"}:
            return None
        rank = token[:-1]
        return rank if rank in {"3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2"} else None

    @staticmethod
    def _rank_from_public_declaration(token: object) -> str | None:
        if not isinstance(token, str):
            return None
        if token in {"SJ", "BJ"}:
            return token
        if token in {"3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A", "2"}:
            return token
        return RAGAdvisor._rank_from_public_token(token)

    @classmethod
    def _candidate_applicability(
        cls,
        observation: dict[str, object],
        legal_actions: list[dict[str, object]],
    ) -> dict[str, bool] | None:
        """Derive prerequisite opportunities from complete public canonical actions.

        This is intentionally an activation gate, not a score or an action
        selector.  A malformed payload leaves every conditional experience
        inactive instead of inferring an opportunity from prose or metadata.
        """
        facts = summarize_candidate_structures(observation, legal_actions)
        if facts is None or len(facts) != len(legal_actions):
            return None
        actions_by_id: dict[int, dict[str, object]] = {}
        for action in legal_actions:
            action_id = action.get("action_id") if isinstance(action, dict) else None
            if type(action_id) is not int or action_id in actions_by_id:
                return None
            actions_by_id[action_id] = action

        has_bomb_or_wildcard = any(
            fact.pattern in {"bomb", "joker_bomb"} or fact.uses_wildcard
            for fact in facts
        )
        has_natural_pair = False
        for fact in facts:
            if fact.pattern != "pair" or fact.uses_wildcard or fact.carrier_count != 2:
                continue
            action = actions_by_id.get(fact.action_id)
            if action is None:
                return None
            carrier = action.get("carrier_cards")
            declared = action.get("declared_cards")
            if not isinstance(carrier, list) or not isinstance(declared, list) or len(carrier) != 2 or len(declared) != 2:
                return None
            carrier_ranks = [cls._rank_from_public_token(card) for card in carrier]
            declared_ranks = [cls._rank_from_public_declaration(card) for card in declared]
            if (
                all(isinstance(rank, str) for rank in carrier_ranks + declared_ranks)
                and len(set(carrier_ranks)) == 1
                and set(carrier_ranks) == set(declared_ranks)
                and carrier_ranks[0] not in {"SJ", "BJ"}
            ):
                has_natural_pair = True
        contrasts = summarize_candidate_contrasts(observation, legal_actions)
        if contrasts is None:
            return None
        contrast_kinds = {contrast.kind for contrast in contrasts}
        current_round = observation.get("current_round")
        try:
            is_opening_free_lead = (
                classify_game_phase(observation).phase == "opening"
                and isinstance(current_round, dict)
                and current_round.get("constraint") == "free"
                and current_round.get("table_action") is None
            )
        except Exception:
            is_opening_free_lead = False
        has_structure_safe_opening_shape = is_opening_free_lead and any(
            fact.is_free_lead
            and fact.pattern in {"pair", "triple", "straight"}
            and not fact.uses_wildcard
            and not fact.fragments_played_rank_group
            and not fact.finishes_hand
            for fact in facts
        )
        return {
            "bomb_or_wildcard": has_bomb_or_wildcard,
            "natural_pair": has_natural_pair,
            "opening_natural_shape": has_structure_safe_opening_shape,
            **{
                kind: kind in contrast_kinds
                for kind in _CANDIDATE_REQUIREMENTS
                if kind not in {"bomb_or_wildcard", "natural_pair", "opening_natural_shape"}
            },
        }

    @classmethod
    def _requirements_match(
        cls,
        metadata: dict[str, str],
        applicability: dict[str, bool] | None,
    ) -> bool:
        raw = metadata.get("candidate_requirements")
        if raw is None:
            return True
        requirements = cls._metadata_values(metadata, "candidate_requirements")
        return bool(
            applicability is not None
            and requirements
            and requirements.issubset(_CANDIDATE_REQUIREMENTS)
            and all(applicability.get(requirement) is True for requirement in requirements)
        )

    @classmethod
    def _matched_requirement_count(
        cls,
        metadata: dict[str, str],
        applicability: dict[str, bool] | None,
    ) -> int:
        requirements = cls._metadata_values(metadata, "candidate_requirements")
        if not requirements or applicability is None:
            return 0
        return len(requirements) if all(applicability.get(item) is True for item in requirements) else 0

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
        phase_context: GamePhaseContext | None = None,
        candidate_relation_kinds: tuple[str, ...] = (),
    ) -> dict[str, object]:
        my_info = dict(observation.get("my_info", {}))
        current_round = dict(observation.get("current_round", {}))

        phase_context = phase_context or classify_game_phase(observation)
        hand_count = phase_context.my_hand_count
        phase = phase_context.phase
        constraint = str(current_round.get("constraint", "unknown"))
        table_action = current_round.get("table_action")
        current_level_rank = str(current_round.get("current_level_rank", ""))

        if is_endgame_phase(phase):
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
            "candidate_relation_kinds": ",".join(candidate_relation_kinds),
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
        relations = set(RAGAdvisor._metadata_values(scene_tags, "candidate_relation_kinds"))
        if relations & {"natural_single_cost", "single_control_resource"}:
            topics.update({"opening", "singles", "control", "probe"})
        if relations & {
            "natural_pair_single", "natural_group_single", "sequence_structure_loss",
            "natural_sequence_single",
            "triple_split_repartition", "triple_pair_kicker_gradient",
        }:
            topics.update({"pair", "structure", "probe"})
        if "natural_sequence_single" in relations:
            topics.update({"straight", "singles"})
            if scene == "lead_opening" and phase == "opening":
                topics.add("opening")
        if "straight_strength" in relations:
            topics.update({"straight", "structure", "control"})
        if "steel_plate_strength" in relations:
            topics.update({"steel_plate", "structure", "control"})
        if "straight_flush_bomb_fragment" in relations:
            topics.update({"bomb", "straight_flush", "structure", "control"})
        if "bomb_residual" in relations:
            topics.update({"bomb", "structure", "control"})
        if "bomb_strength_resource" in relations:
            topics.update({"bomb", "structure", "control", "resource"})
        if "wildcard_resource" in relations:
            topics.update({"wildcard", "structure", "control"})
        if relations & {"teammate_control_resource", "teammate_table_choice"}:
            topics.update({"teammate", "support", "control", "pass"})
        if relations & {"danger_block_resource", "danger_block_choice"}:
            topics.update({"opponent_pressure", "block", "control"})
        intent = str(scene_tags.get("strategy_intent", ""))
        if intent == "support_teammate":
            topics.update({"teammate", "support"})
        elif intent == "block_opponent":
            topics.update({"opponent_pressure", "block"})
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
        relation_terms = {
            "natural_single_cost": "低成本单张 中间单张",
            "single_control_resource": "自然小单 控制牌 回手",
            "natural_pair_single": "自然对子 单张 拆组 清理",
            "natural_group_single": "自然对子 三张 普通单张 清理 余组",
            "natural_sequence_single": "自然顺子 顺子内自然单张 清理 低成本试探 残余结构",
            "straight_strength": "小顺 大顺 强弱 清理 保留 余组",
            "sequence_structure_loss": "顺子 拆组 残余对子 三张 余组",
            "triple_split_repartition": "三张 拆单 三带二 两组牌结构 重组",
            "straight_flush_bomb_fragment": "同花顺 拆炸弹 自然炸弹 结构资源",
            "steel_plate_strength": "钢板 大小 强度 保留 清理",
            "triple_pair_kicker_gradient": "三带二 携带对子 梯度 余组",
            "bomb_residual": "自然炸弹 不同长度 出后残余 点数组 自然组合 用途",
            "bomb_strength_resource": "自然小炸弹 大炸 强度 控制 资源成本 余组",
            "wildcard_resource": "逢人配 自然路线 通配资源",
            "teammate_control_resource": "队友控桌 pass 让牌 控制资源",
            "teammate_table_choice": "队友控桌 pass 让牌 争夺牌权",
            "danger_block_resource": "危险对手 阻断 pass 控制资源",
            "danger_block_choice": "危险对手 阻断 pass 合法压制",
        }
        for relation in RAGAdvisor._metadata_values(scene_tags, "candidate_relation_kinds"):
            if relation in relation_terms:
                zh_terms.extend(relation_terms[relation].split())
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
    def _phase_tag_match_score(doc_values: set[str], phase: str, exact_weight: float, any_weight: float) -> float | None:
        if not doc_values:
            return None
        if any(phase_matches(phase, candidate) for candidate in doc_values):
            return exact_weight
        if "any" in doc_values:
            return any_weight
        if phase == "unknown" and "unknown" in doc_values:
            return any_weight
        return None

    @staticmethod
    def _keyword_score(doc: KnowledgeDocument, query: str, desired_topics: set[str]) -> float:
        score = 0.0
        metadata = {
            key: value
            for key, value in doc.metadata.items()
            if key in _KNOWLEDGE_METADATA_KEYS
        }
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
        candidate_applicability: dict[str, bool] | None,
    ) -> tuple[float, str, str] | None:
        if not cls._requirements_match(doc.metadata, candidate_applicability):
            return None
        semantic_metadata = " ".join(
            value
            for key, value in doc.metadata.items()
            if key in _KNOWLEDGE_METADATA_KEYS
        )
        combined_text = f"{doc.content} {semantic_metadata}"
        status, reason = cls._mark_conflict(combined_text)
        if status != "accepted":
            return None

        score = 0.0
        for key, (exact_weight, any_weight) in _TAG_WEIGHTS.items():
            wanted = str(scene_tags.get(key, "unknown"))
            doc_values = cls._metadata_values(doc.metadata, key)
            if key == "phase":
                tag_score = cls._phase_tag_match_score(doc_values, wanted, exact_weight, any_weight)
            else:
                tag_score = cls._tag_match_score(doc_values, wanted, exact_weight, any_weight)
            if tag_score is None:
                return None
            score += tag_score

        score += cls._keyword_score(doc, query, desired_topics)
        # A fully satisfied, source-authored candidate gate is positive
        # evidence that this claim belongs in the current context.  This
        # remains semantic metadata; provenance never participates in scoring.
        score += 18.0 * cls._matched_requirement_count(doc.metadata, candidate_applicability)
        requested_domains = cls._metadata_values(scene_tags, "strategy_domains")
        doc_domains = cls._metadata_values(doc.metadata, "strategy_domain")
        # Domains are public runtime semantics, not provenance.  They provide
        # a deterministic tie-break/boost without excluding a valid fallback.
        score += 12.0 * len(requested_domains & doc_domains)
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
        candidate_applicability: dict[str, bool] | None,
    ) -> tuple[RAGEvidence, ...]:
        if top_k <= 0:
            return ()

        desired_topics = self._topics_from_scene_tags(scene_tags)
        candidates: list[tuple[int, float, int, KnowledgeDocument, bool]] = []
        active_relations = self._metadata_values(scene_tags, "candidate_relation_kinds")
        opening_free_lead = (
            layer == "experience"
            and scene_tags.get("scene") == "lead_opening"
            and scene_tags.get("phase") == "opening"
            and scene_tags.get("action_context") == "free_lead"
        )
        for idx, doc in enumerate(self._retriever.documents):
            if doc.layer != layer:
                continue
            scored = self._tag_score_document(
                doc,
                scene_tags=scene_tags,
                query=query,
                desired_topics=desired_topics,
                candidate_applicability=candidate_applicability,
            )
            if scored is None:
                continue
            score, _, _ = scored
            document_requirements = self._metadata_values(doc.metadata, "candidate_requirements")
            exact_relations = active_relations & document_requirements & _RELATION_SPECIFIC_SOFT_REQUIREMENTS
            if "natural_pair" in document_requirements:
                exact_relations.update(
                    active_relations & {"natural_pair_single", "natural_group_single"}
                )
            if "bomb_or_wildcard" in document_requirements:
                if "bomb_strength_resource" in active_relations:
                    exact_relations.add("bomb_strength_resource")
                if "bomb_residual" in active_relations:
                    exact_relations.add("bomb_residual")
            # In an opening free lead, reserve one top slot for an applicable
            # source principle so top_k=1 (the production factory default)
            # still has an authored opening basis. Remaining slots retain the
            # normal relationship/score order, so this does not crowd out all
            # matching soft hypotheses at larger top_k values. This only
            # reorders already-admitted semantic candidates; provenance never
            # participates.
            is_opening_source_principle = (
                opening_free_lead
                and doc.metadata.get("guidance_mode") == "source_principle"
                and "opening_free_lead"
                in self._metadata_values(doc.metadata, "strategy_domain")
            )
            candidates.append((0 if exact_relations else 1, -score, idx, doc, is_opening_source_principle))

        candidates.sort(key=lambda item: (item[0], item[1], item[2]))
        if opening_free_lead:
            source_index = next(
                (index for index, item in enumerate(candidates) if item[4]),
                None,
            )
            if source_index is not None and source_index > 0:
                candidates.insert(0, candidates.pop(source_index))

        evidence: list[RAGEvidence] = []
        for _, negative_score, _, doc, _ in candidates[:top_k]:
            score = -negative_score
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
        metadata = {
            key: value
            for key, value in evidence.metadata.items()
            if key in _KNOWLEDGE_METADATA_KEYS | {"source_path", "status", "score", "reason"}
        }
        return {
            "source_id": evidence.source_id,
            "layer": evidence.layer,
            "snippet": RAGAdvisor._clip(evidence.snippet),
            "metadata": metadata,
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
            semantic_metadata = " ".join(
                value
                for key, value in hit.metadata.items()
                if key in _KNOWLEDGE_METADATA_KEYS
            )
            status, reason = self._mark_conflict(f"{hit.snippet} {semantic_metadata}")
            metadata = {
                "source_path": hit.source_path,
                "status": status,
            }
            metadata.update(
                {
                    key: value
                    for key, value in hit.metadata.items()
                    if key in _KNOWLEDGE_METADATA_KEYS
                }
            )
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
            if not self._requirements_match(hit.metadata, None):
                continue
            semantic_metadata = " ".join(
                value
                for key, value in hit.metadata.items()
                if key in _KNOWLEDGE_METADATA_KEYS
            )
            status, reason = self._mark_conflict(f"{hit.snippet} {semantic_metadata}")
            metadata = {
                "source_path": hit.source_path,
                "status": status,
            }
            metadata.update(
                {
                    key: value
                    for key, value in hit.metadata.items()
                    if key in _KNOWLEDGE_METADATA_KEYS
                }
            )
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
        phase_context: GamePhaseContext | None = None,
        strategy_context: object = None,
        strategy_recommendation: object = None,
    ) -> dict[str, object]:
        from agents.action_structure import summarize_candidate_contrasts

        contrasts = summarize_candidate_contrasts(observation, legal_actions)
        relation_kinds = (
            tuple(dict.fromkeys(item.kind for item in contrasts))
            if contrasts is not None
            else ()
        )
        scene_tags = self._scene_tags(
            observation, legal_actions, hand_eval, phase_context, relation_kinds
        )
        candidate_applicability = self._candidate_applicability(observation, legal_actions)
        intent = getattr(strategy_context, "intent", None)
        if isinstance(intent, str) and intent in {"run_out", "control", "support_teammate", "block_opponent"}:
            scene_tags["strategy_intent"] = intent
        domains = getattr(strategy_recommendation, "strategy_domains", None)
        if isinstance(domains, tuple) and all(type(domain) is str for domain in domains):
            from agents.strategy_recommendation import STRATEGY_DOMAINS
            if tuple(domain for domain in STRATEGY_DOMAINS if domain in domains) == domains:
                scene_tags["strategy_domains"] = ",".join(domains)
        query = self.build_query(scene_tags)

        try:
            rule_evidence = self._retrieve_tagged(
                layer="rule",
                scene_tags=scene_tags,
                query=query,
                top_k=top_k,
                candidate_applicability=candidate_applicability,
            )
        except Exception:
            rule_evidence = ()

        try:
            experience_evidence = self._retrieve_tagged(
                layer="experience",
                scene_tags=scene_tags,
                query=query,
                top_k=top_k,
                candidate_applicability=candidate_applicability,
            )
        except Exception:
            experience_evidence = ()

        return {
            "scene_tags": scene_tags,
            "rule_hits": self._accepted(rule_evidence),
            "experience_hits": self._accepted(experience_evidence),
            "query": query,
        }
