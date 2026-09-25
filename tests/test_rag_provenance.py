import json
from pathlib import Path
import tempfile
import unittest

from agents.deepseek_client import DeepSeekClient
from agents.rag_advisor import RAGAdvisor
from rag.kb_loader import KnowledgeBaseLoader
from rag.retriever import KnowledgeRetriever


_CORPUS_TEMPLATE = """---
id: {entry_id}
corpus: experience
scene: [lead_opening]
phase: [opening]
hand_strength: [strong]
action_context: [free_lead]
topic: [opening, control]
priority: high
keywords_cn: [强牌, 小单]
---

# 公开策略

强控制且有回手资源时，可考虑不拆组合的自然小单。
"""


def _scope(*, scene: str = "lead_opening", level_rank: str = "any") -> dict[str, object]:
    return {
        "game_scope": "single_game",
        "player_count": 4,
        "tribute": "none",
        "level_rank": level_rank,
        "scenes": [scene],
    }


def _record(
    entry_id: str,
    *,
    status: str = "active",
    tier: str = "B",
    claim_type: str = "strategy",
    scope: dict[str, object] | None = None,
    marker: str = "audit-marker-a",
) -> dict[str, object]:
    return {
        "entry_id": entry_id,
        "source_tier": tier,
        "claim_type": claim_type,
        "author_or_institution": f"author-{marker}",
        "title": f"title-{marker}",
        "publication": f"publication-{marker}",
        "url_or_bibliography": f"https://example.invalid/{marker}",
        "locator": f"locator-{marker}",
        "scope": scope or _scope(),
        "evidence_status": status,
    }


def _write_rag(root: Path, documents: list[str], records: list[dict[str, object]]) -> None:
    corpus_dir = root / "experience_corpus"
    corpus_dir.mkdir(parents=True)
    (corpus_dir / "basic_human_experience.md").write_text("\n\n".join(documents), encoding="utf-8")
    (root / "experience_provenance.json").write_text(
        json.dumps(
            {"schema": "guandan_experience_provenance", "version": 1, "records": records},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _context_and_prompt(root: Path) -> tuple[dict[str, object], str]:
    documents = KnowledgeBaseLoader(root).load_experience_documents()
    advisor = RAGAdvisor(KnowledgeRetriever(documents))
    observation = {
        "my_info": {
            "player_id": 1,
            "team": "1&3",
            "hand_cards": ["4S", "QS", "SJ", "BJ"]
            + [
                card
                for rank in ("3", "5", "6", "7", "8", "9", "10", "J")
                for card in (f"{rank}S", f"{rank}H")
            ],
            "hand_count": 20,
        },
        "current_round": {
            "step_no": 0,
            "round_no": 1,
            "current_player_id": 1,
            "current_level_rank": "2",
            "constraint": "free",
            "table_action": None,
        },
        "other_players": [
            {"player_id": 2, "team": "2&4", "hand_count": 20, "finished": False, "finish_rank": None},
            {"player_id": 3, "team": "1&3", "hand_count": 20, "finished": False, "finish_rank": None},
            {"player_id": 4, "team": "2&4", "hand_count": 20, "finished": False, "finish_rank": None},
        ],
        "history": {"actions": [], "finish_order": []},
    }
    actions = [
        {
            "action_id": 1,
            "declared_pattern": "single",
            "declared_cards": ["4"],
            "carrier_cards": ["4S"],
            "wildcard_count": 0,
            "wildcard_info": [],
            "display_text": "single:4",
        }
    ]
    context = advisor.get_rag_context(
        observation=observation,
        legal_actions=actions,
        hand_eval={"label": "strong"},
    )
    prompt = DeepSeekClient._build_structured_prompt(
        my_info=observation["my_info"],
        current_round=observation["current_round"],
        other_players=observation["other_players"],
        history=observation["history"],
        legal_actions=actions,
        rag_context=context,
    )
    return context, prompt


class TestExperienceProvenance(unittest.TestCase):
    def test_only_complete_supported_active_records_load(self) -> None:
        ids = [
            "active",
            "candidate",
            "registry",
            "missing",
            "unknown_tier",
            "unknown_status",
            "conflict",
            "governance_in_text",
            "malformed_metadata",
            "unknown_candidate_requirement",
            "duplicate",
            "duplicate",
        ]
        documents = [_CORPUS_TEMPLATE.format(entry_id=entry_id) for entry_id in ids]
        governance_index = ids.index("governance_in_text")
        documents[governance_index] = documents[governance_index].replace(
            "keywords_cn: [强牌, 小单]",
            "keywords_cn: [强牌, 小单]\nauthor: should-not-be-front-matter",
        )
        malformed_index = ids.index("malformed_metadata")
        documents[malformed_index] = documents[malformed_index].replace(
            "priority: high",
            "priority: unsupported",
        )
        unknown_requirement_index = ids.index("unknown_candidate_requirement")
        documents[unknown_requirement_index] = documents[unknown_requirement_index].replace(
            "keywords_cn: [强牌, 小单]",
            "keywords_cn: [强牌, 小单]\ncandidate_requirements: [unsupported_requirement]",
        )
        records = [
            _record("active"),
            _record("candidate", status="candidate", tier="C"),
            _record("registry", status="registry_only", claim_type="publication_record"),
            _record("unknown_tier", tier="unknown"),
            _record("unknown_status", status="published"),
            _record("conflict", scope=_scope(level_rank="A")),
            _record("governance_in_text"),
            _record("malformed_metadata"),
            _record("unknown_candidate_requirement"),
            _record("duplicate"),
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_rag(root, documents, records)
            loaded = KnowledgeBaseLoader(root).load_experience_documents()

        self.assertEqual([doc.doc_id for doc in loaded], ["active"])

    def test_missing_registry_or_required_field_degrades_to_no_experience(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_rag(root, [_CORPUS_TEMPLATE.format(entry_id="active")], [_record("active")])
            registry = json.loads((root / "experience_provenance.json").read_text(encoding="utf-8"))
            del registry["records"][0]["title"]
            (root / "experience_provenance.json").write_text(json.dumps(registry), encoding="utf-8")
            self.assertEqual(KnowledgeBaseLoader(root).load_experience_documents(), ())
            (root / "experience_provenance.json").unlink()
            self.assertEqual(KnowledgeBaseLoader(root).load_experience_documents(), ())

    def test_corroborating_registry_links_must_resolve_to_active_strategy_sources(self) -> None:
        document = _CORPUS_TEMPLATE.format(entry_id="active")
        linked = _record("active")
        linked["corroborating_source_ids"] = ["missing-source"]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_rag(root, [document], [linked])
            self.assertEqual(KnowledgeBaseLoader(root).load_experience_documents(), ())

        linked = _record("active")
        registry_only = _record("registry-only", status="registry_only", claim_type="publication_record")
        linked["corroborating_source_ids"] = ["registry-only"]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_rag(root, [document], [linked, registry_only])
            self.assertEqual(KnowledgeBaseLoader(root).load_experience_documents(), ())

    def test_governance_changes_do_not_change_retrieval_or_prompt_bytes(self) -> None:
        outputs: list[tuple[dict[str, object], str]] = []
        for marker in ("audit-marker-a", "audit-marker-b"):
            with tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                _write_rag(
                    root,
                    [_CORPUS_TEMPLATE.format(entry_id="opaque-active-id")],
                    [_record("opaque-active-id", marker=marker)],
                )
                outputs.append(_context_and_prompt(root))

        self.assertEqual(outputs[0], outputs[1])
        context, prompt = outputs[0]
        self.assertEqual(len(context["experience_hits"]), 1)
        for forbidden in (
            "audit-marker-a",
            "author_or_institution",
            "url_or_bibliography",
            "locator",
            "source_tier",
            "evidence_status",
        ):
            self.assertNotIn(forbidden, json.dumps(context, ensure_ascii=False))
            self.assertNotIn(forbidden, prompt)
        self.assertNotIn("opaque-active-id", prompt)

    def test_real_registry_has_active_candidate_and_registry_only_without_governance_leak(self) -> None:
        root = Path("rag")
        registry = json.loads((root / "experience_provenance.json").read_text(encoding="utf-8"))
        statuses = {record["evidence_status"] for record in registry["records"]}
        loaded = KnowledgeBaseLoader(root).load_experience_documents()

        self.assertEqual(statuses, {"active", "candidate", "registry_only"})
        self.assertEqual(
            {doc.doc_id for doc in loaded},
            {
                "exp_general_boundary_001",
                "exp_lead_opening_strong_001",
                "exp_lead_opening_medium_001",
                "exp_lead_opening_shape_001",
                "exp_lead_opening_weak_001",
                "exp_midgame_control_001",
                "exp_midgame_teammate_001",
                "exp_midgame_block_001",
                "exp_bomb_wildcard_001",
                "exp_endgame_run_out_001",
                "exp_card_memory_001",
                "exp_soft_pair_probe_001",
                "exp_soft_single_cost_probe_001",
                "exp_soft_straight_flush_bomb_cost_001",
                "exp_soft_steel_plate_strength_001",
                "exp_soft_triple_pair_gradient_001",
                "exp_soft_triple_repartition_001",
            },
        )
        for doc in loaded:
            self.assertFalse(
                {"author_or_institution", "title", "publication", "url_or_bibliography", "locator", "source_tier", "evidence_status"}
                & set(doc.metadata)
            )

    def test_active_corpus_covers_ten_domains_and_marks_soft_hypothesis(self) -> None:
        loaded = KnowledgeBaseLoader(Path("rag")).load_experience_documents()
        domains = {
            domain
            for doc in loaded
            for domain in doc.metadata.get("strategy_domain", "").split(",")
            if domain
        }
        self.assertEqual(
            domains,
            {
                "overall_priority", "opening_free_lead", "hand_structure", "control_return_resource",
                "follow_control", "teammate_coordination", "danger_opponent_block",
                "bomb_wildcard_management", "endgame_planning", "uncertainty_probe",
            },
        )
        soft = [doc for doc in loaded if doc.metadata.get("guidance_mode") == "soft_hypothesis"]
        self.assertEqual(
            [doc.doc_id for doc in soft],
            [
                "exp_bomb_wildcard_001", "exp_soft_pair_probe_001", "exp_soft_single_cost_probe_001",
                "exp_soft_straight_flush_bomb_cost_001", "exp_soft_steel_plate_strength_001",
                "exp_soft_triple_pair_gradient_001", "exp_soft_triple_repartition_001",
            ],
        )
        records = {record["entry_id"]: record for record in json.loads((Path("rag") / "experience_provenance.json").read_text(encoding="utf-8"))["records"]}
        self.assertEqual(records["exp_bomb_wildcard_001"]["source_tier"], "C")
        self.assertEqual(
            set(records["exp_bomb_wildcard_001"]["corroborating_source_ids"]),
            {
                "source_guandanmaster_bomb_timing_001",
                "candidate_smzdm_strategy_100_001",
                "source_user_supplied_strategy_100_001",
            },
        )
        self.assertEqual(
            records["source_user_supplied_strategy_100_001"]["evidence_status"],
            "active",
        )
        for entry_id in (
            "exp_soft_straight_flush_bomb_cost_001",
            "exp_soft_steel_plate_strength_001",
            "exp_soft_triple_pair_gradient_001",
            "exp_soft_triple_repartition_001",
        ):
            self.assertEqual(
                set(records[entry_id]["corroborating_source_ids"]),
                {"candidate_smzdm_strategy_100_001", "source_user_supplied_strategy_100_001"},
            )


if __name__ == "__main__":
    unittest.main()
