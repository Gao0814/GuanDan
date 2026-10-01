from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import io
import os
import re
from random import Random
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from agents.deepseek_client import DeepSeekClient
from integrations.botzone.__main__ import _manual_game_evidence_path
from integrations.botzone.connector import MockConnector
from integrations.botzone.game_evidence import (
    GAME_EVIDENCE_INDEX,
    GameEvidenceError,
    ManualGameEvidenceRecorder,
    prepare_game_evidence,
)
from integrations.botzone.game_results import GameResultRecorder
from integrations.botzone.models import GlobalState
from integrations.botzone.play_adapter import NoTributeRuleBasedHandler
from integrations.botzone.runner import ForegroundRunner
from integrations.botzone.session import SessionStore
from integrations.botzone.agent_runtime import build_agent_factory
from tests.test_botzone_deepseek_agent_runtime import _config


def _deal_inner() -> dict[str, object]:
    return {
        "stage": "deal",
        "deliver": list(range(27)),
        "your_id": 0,
        "global": {"level": "2", "tribute": 0, "first": None, "last": None},
    }


def _deal() -> str:
    return json.dumps({"requests": [_deal_inner()], "responses": []}, separators=(",", ":"))


def _play() -> str:
    play = {
        "stage": "play",
        "history": [[], [], [], []],
        "done": [],
        "pass_on": -1,
        "global": {
            "level": "2",
            "tribute": 0,
            "first": None,
            "last": None,
            "resist": False,
            "tribute_cards": {},
            "return_cards": {},
        },
    }
    return json.dumps({"requests": [_deal_inner(), play], "responses": [[]]}, separators=(",", ":"))


def _play_after_action(action_response: list[list[int]]) -> str:
    empty_history_play = {
        "stage": "play", "history": [[], [], [], []], "done": [], "pass_on": -1,
        "global": {"level": "2", "tribute": 0, "first": None, "last": None, "resist": False,
                   "tribute_cards": {}, "return_cards": {}},
    }
    observed_play = {
        **empty_history_play,
        "history": [[], [], [], {"player": 0, "response": action_response}],
    }
    return json.dumps(
        {"requests": [_deal_inner(), empty_history_play, observed_play], "responses": [[], action_response]},
        separators=(",", ":"),
    )


class _FakePollTransport:
    def __init__(self, polls: list[bytes]) -> None:
        self.polls = polls
        self.headers: list[dict[str, bytes]] = []

    def poll(self, headers: object) -> bytes:
        self.headers.append(dict(headers))
        return self.polls.pop(0)


def _polls_for(first: int, count: int, *, trailing_idle: bool) -> list[bytes]:
    polls: list[bytes] = []
    for game_no in range(first, first + count):
        match = f"evidence-game-{game_no:03d}"
        polls.append(f"1 0\n{match}\n{_deal()}".encode())
        polls.append(f"1 0\n{match}\n{_play()}".encode())
        polls.append(f"0 1\n{match} 0 4 1 0 1 0\n".encode())
        if trailing_idle or game_no != first + count - 1:
            polls.append(b"0 0\n")
    return polls


class BotzoneGameEvidenceTests(unittest.TestCase):
    def test_short_reason_schema_rejects_unbounded_or_failure_fields(self) -> None:
        for override in (
            {"reason": "synthetic-invalid\nreason"}, {"reason": "x" * 121},
            {"reason": ["not-text"]}, {"reason_truncated": "false"},
            {"outcome": "timeout"}, {"content": "forbidden-response-body"},
        ):
            with self.subTest(fields=tuple(override)), TemporaryDirectory() as temporary:
                games = Path(temporary) / "games"
                prepare_game_evidence(games, 10)
                recorder = ManualGameEvidenceRecorder(games)
                recorder.begin_game("synthetic-match", own_hand=(1,), player_id=0,
                    global_state=GlobalState("2", 0, None, None))
                number = recorder.begin_decision("synthetic-match")
                recorder.record_agent_event("synthetic-match", number, "model_complete", {
                    "outcome": "success", "selected_action_id": 1, "reason": "bounded",
                    "reason_truncated": False, **override})
                self.assertEqual(recorder.error_category, "evidence_schema_invalid")
                game_dir = next(p for p in games.iterdir() if p.is_dir())
                timeline = (game_dir / "timeline.jsonl").read_text()
                self.assertNotIn('"event":"model_complete"', timeline)

    def test_factory_short_reason_is_private_bound_to_decision_and_ack(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            games = root / "games"
            prepare_game_evidence(games, 10)
            evidence = ManualGameEvidenceRecorder(games)
            calls = []
            short = "synthetic-short\n" + "🙂" * 121
            deal = _deal_inner()
            deal["deliver"] = Random(17).sample(range(108), 27)

            def dealt_payload(payload):
                value = json.loads(payload)
                value["requests"][0] = deal
                return json.dumps(value)

            def fake_sse(request, _timeout):
                body = json.loads(request.data)
                chosen = int(re.search(r"#(\d+)\s+action_id=", body["messages"][1]["content"]).group(1))
                content = {"action_id": chosen, "extra": "forbidden-extra"}
                if not calls:
                    content["reason"] = short
                calls.append(chosen)
                delta = json.dumps({"choices": [{"delta": {
                    "content": json.dumps(content), "reasoning_content": "forbidden-long-reasoning"}}]})
                return f"data: {delta}\ndata: [DONE]\n"

            class Polls:
                call = 0

                def poll(self, headers):
                    self.call += 1
                    if self.call == 1:
                        return f"1 0\nreason-match\n{dealt_payload(_deal())}".encode()
                    if self.call == 2:
                        return f"1 0\nreason-match\n{dealt_payload(_play())}".encode()
                    if self.call == 3:
                        response = json.loads(next(iter(dict(headers).values())))['response']
                        return f"1 0\nreason-match\n{dealt_payload(_play_after_action(response))}".encode()
                    if self.call == 4:
                        return f"1 0\nother-reason-match\n{dealt_payload(_deal())}".encode()
                    return f"1 0\nother-reason-match\n{dealt_payload(_play())}".encode()

            output = io.StringIO()
            with patch("agents.deepseek_ai.AppConfig.from_env", return_value=_config()), \
                    redirect_stdout(output), redirect_stderr(output):
                factory = build_agent_factory("deepseek", config_loader=_config,
                    client_factory=lambda **kwargs: DeepSeekClient(**kwargs, transport=fake_sse))
                handler = NoTributeRuleBasedHandler(agent_mode="deepseek", agent_factory=factory,
                    decision_trace_enabled=True, game_evidence_recorder=evidence)
                state = SessionStore(root / "state", decision_trace_enabled=True)
                connector = MockConnector(state, Polls(), handler, game_evidence_recorder=evidence)
                for _ in range(5):
                    connector.cycle()
                # An old per-decision callback cannot attach a reason to a newer turn.
                evidence.agent_sink("reason-match", 1)("model_complete", {
                    "outcome": "success", "selected_action_id": calls[0],
                    "reason": "stale-forbidden", "reason_truncated": False})
                connector.close_game_evidence("interrupted")
            directories = sorted(p for p in games.iterdir() if p.is_dir())
            first = directories[0]
            events = [json.loads(line) for line in (first / "timeline.jsonl").read_text().splitlines()]
            completed = [row["data"] for row in events if row["event"] == "model_complete"]
            decisions = [json.loads(line)["data"] for line in (first / "decisions.jsonl").read_text().splitlines()]
            self.assertEqual(len(completed), 2)
            self.assertEqual(completed[0]["reason"], "synthetic-short " + "🙂" * 104)
            self.assertTrue(completed[0]["reason_truncated"])
            self.assertIsNone(completed[1]["reason"])
            for result, decision in zip(completed, decisions):
                self.assertEqual(result["decision_no"], decision["evidence_decision_no"])
                self.assertEqual(result["selected_action_id"], decision["selected_action_id"])
                self.assertEqual(decision["decision_source"], "model")
            ack = next(row["data"] for row in events if row["event"] == "ack_confirmed"
                       and "selected_action_id" in row["data"])
            self.assertEqual(ack["selected_action_id"], completed[0]["selected_action_id"])
            second_events = [json.loads(line) for line in (directories[1] / "timeline.jsonl").read_text().splitlines()]
            self.assertIsNone(next(row["data"]["reason"] for row in second_events if row["event"] == "model_complete"))
            all_evidence = b"".join(p.read_bytes() for p in games.rglob("*") if p.is_file())
            for forbidden in (b"forbidden-long-reasoning", b"forbidden-extra", b"stale-forbidden"):
                self.assertNotIn(forbidden, all_evidence)
            state_bytes = b"".join(p.read_bytes() for p in (root / "state").rglob("*") if p.is_file())
            self.assertNotIn(b"synthetic-short", state_bytes)
            self.assertNotIn("synthetic-short", output.getvalue())
            # Reopening accepts new optional fields alongside all existing rows.
            prepare_game_evidence(games, 10)

    def _run_fake_batch_segment(self, root: Path, games_root: Path, first: int, count: int) -> None:
        store = ManualGameEvidenceRecorder(games_root)
        state = SessionStore(root / "state", decision_trace_enabled=True)
        transport = _FakePollTransport(_polls_for(first, count, trailing_idle=False))
        handler = NoTributeRuleBasedHandler(
            agent_mode="rule",
            decision_trace_enabled=True,
            game_evidence_recorder=store,
        )
        connector = MockConnector(
            state,
            transport,
            handler,
            game_result_recorder=GameResultRecorder(root / f"results-{first}.jsonl"),
            game_evidence_recorder=store,
        )
        runner = ForegroundRunner(
            connector,
            max_consecutive_failures=3,
            backoff_seconds=0,
            sleep=lambda _seconds: None,
            clock=lambda: 0.0,
        )
        summary = runner.run(
            max_cycles=count * 4 - 1,
            max_wall_seconds=None,
            stop_after_finished=None,
        )
        self.assertEqual(summary.finished_qualified, count)
        self.assertEqual(summary.game_evidence_status, "ok")
        self.assertEqual(transport.polls, [])

    def test_fake_connector_crosses_idle_and_two_starts_and_rotates_eleven_games_to_ten(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            workspace = root / "workspace"
            workspace.mkdir()
            old_run = workspace / "manual-batch-old"
            old_run.mkdir()
            old_file = old_run / "sentinel.bin"
            old_bytes = b"old run remains byte exact\x00"
            old_file.write_bytes(old_bytes)
            games_root = workspace / "games"
            prepare_game_evidence(games_root, 10)

            # One active connector handles the first seven games. A second
            # simulated launch resumes the same managed rolling store.
            self._run_fake_batch_segment(root, games_root, 1, 7)
            idle_connector = _FakePollTransport([b"0 0\n"])
            idle = MockConnector(
                SessionStore(root / "state", decision_trace_enabled=True),
                idle_connector,
                lambda _context: None,
                game_evidence_recorder=ManualGameEvidenceRecorder(games_root),
            )
            self.assertEqual(idle.cycle().requests_seen, 0)
            self._run_fake_batch_segment(root, games_root, 8, 5)

            index = json.loads((games_root / GAME_EVIDENCE_INDEX).read_text(encoding="utf-8"))
            directories = sorted(path for path in games_root.iterdir() if path.is_dir())
            retained_sample = games_root / index["entries"][0]["directory"]
            sample_observations = [json.loads(line) for line in (retained_sample / "observations.jsonl").read_text(encoding="utf-8").splitlines()]
            sample_decisions = [json.loads(line) for line in (retained_sample / "decisions.jsonl").read_text(encoding="utf-8").splitlines()]
            sample_events = [json.loads(line) for line in (retained_sample / "timeline.jsonl").read_text(encoding="utf-8").splitlines()]
            serialized = b"".join(path.read_bytes() for path in games_root.rglob("*") if path.is_file())
            after_old = old_file.read_bytes()

        self.assertEqual([entry["game_no"] for entry in index["entries"]], list(range(3, 13)))
        self.assertEqual(index["next_game_no"], 12)
        self.assertEqual(len(directories), 10)
        self.assertTrue(all("_" in path.name and ":" not in path.name for path in directories))
        self.assertTrue(all(path.name[-6:].isdigit() for path in directories))
        self.assertEqual(after_old, old_bytes)
        self.assertNotIn(b"evidence-game-", serialized)
        self.assertTrue(all(entry["status"] == "finished" for entry in index["entries"]))
        self.assertEqual(sample_observations[0]["data"]["observation_scope"], "connector_observed_only")
        self.assertTrue(sample_observations[0]["data"]["own_hand"])
        trace = sample_decisions[0]["data"]
        self.assertTrue(trace["observation"]["my_info"]["hand_cards"])
        legal_ids = {action["action_id"] for action in trace["legal_actions"]}
        self.assertGreater(len(legal_ids), 1)
        self.assertIn(trace["selected_action_id"], legal_ids)
        self.assertEqual(trace["selected_action"]["action_id"], trace["selected_action_id"])
        self.assertEqual(trace["decision_source"], "rule_primary")
        event_names = [event["event"] for event in sample_events]
        self.assertIn("action_computed", event_names)
        self.assertIn("header_pending", event_names)
        self.assertIn("ack_confirmed", event_names)

    def test_same_second_names_use_a_monotonic_sequence_and_private_manifest(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            games = root / "games"
            prepare_game_evidence(games, 10)
            recorder = ManualGameEvidenceRecorder(
                games,
                clock=lambda: datetime(2026, 9, 28, 12, 34, 56, tzinfo=timezone.utc),
            )
            global_state = GlobalState("2", 0, None, None)
            for match in ("private-match-one", "private-match-two"):
                recorder.begin_game(match, own_hand=(1, 2, 3), player_id=0, global_state=global_state)
                recorder.record_unconfirmed(match)
            recorder.close("interrupted")
            entries = json.loads((games / GAME_EVIDENCE_INDEX).read_text(encoding="utf-8"))["entries"]
            names = [entry["directory"] for entry in entries]
            bytes_on_disk = b"".join(path.read_bytes() for path in games.rglob("*") if path.is_file())

        local = datetime(2026, 9, 28, 12, 34, 56, tzinfo=timezone.utc).astimezone()
        prefix = f"{local.year}_{local.month}_{local.day}_{local.hour:02d}-{local.minute:02d}-{local.second:02d}"
        self.assertEqual(names, [f"{prefix}_000001", f"{prefix}_000002"])
        self.assertEqual([entry["status"] for entry in entries], ["finished_unconfirmed"] * 2)
        self.assertNotIn(b"private-match-one", bytes_on_disk)
        self.assertNotIn(b"private-match-two", bytes_on_disk)

    def test_old_recent_summary_import_is_once_only_and_source_bytes_are_unchanged(self) -> None:
        from integrations.botzone.rolling_results import (
            RollingGameResultRecorder,
            prepare_recent_results,
            recent_results_paths,
        )

        with TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "BotzoneWorkspace"
            workspace.mkdir()
            _, recent_path, _ = recent_results_paths(workspace)
            prepare_recent_results(workspace, 10, allow_legacy_scan=False)
            old = RollingGameResultRecorder(recent_path, 10)
            for result in ("local_team_win", "platform_error", "local_team_loss"):
                old.record_finished(result)
            old.close()
            original = recent_path.read_bytes()
            games = workspace / "games"
            prepare_game_evidence(games, 10, legacy_recent_results=recent_path)
            first = json.loads((games / GAME_EVIDENCE_INDEX).read_text(encoding="utf-8"))
            prepare_game_evidence(games, 10, legacy_recent_results=recent_path)
            second = json.loads((games / GAME_EVIDENCE_INDEX).read_text(encoding="utf-8"))
            self.assertEqual(recent_path.read_bytes(), original)
            recorder = ManualGameEvidenceRecorder(games)
            recorder.begin_game("new-match", own_hand=(1,), player_id=0, global_state=GlobalState("2", 0, None, None))
            state = json.loads((games / GAME_EVIDENCE_INDEX).read_text(encoding="utf-8"))
            recorder.record_unconfirmed("new-match")
            recorder.close()

        self.assertEqual(first["entries"], second["entries"])
        self.assertEqual(len(first["entries"]), 3)
        self.assertTrue(all(entry["kind"] == "summary_only" for entry in first["entries"]))
        self.assertEqual(state["next_game_no"], 4)
        self.assertEqual(state["entries"][-1]["game_no"], 4)

    def test_restart_marks_stale_active_game_unconfirmed_and_reuses_its_identity(self) -> None:
        with TemporaryDirectory() as temporary:
            games = Path(temporary) / "games"
            prepare_game_evidence(games, 10)
            first = ManualGameEvidenceRecorder(games)
            first.begin_game(
                "restart-match", own_hand=(1, 2), player_id=0,
                global_state=GlobalState("2", 0, None, None),
            )
            game_directory = next(path for path in games.iterdir() if path.is_dir())

            # A new launcher only prepares the store after its process guard
            # succeeds, so an in_progress row here is a prior interrupted run.
            next_game_no, retained = prepare_game_evidence(games, 10)
            manifest_after_restart = json.loads((game_directory / "manifest.json").read_text(encoding="utf-8"))
            resumed = ManualGameEvidenceRecorder(games)
            resumed.begin_game(
                "restart-match", own_hand=(1,), player_id=0,
                global_state=GlobalState("2", 0, None, None),
            )
            manifest_after_resume = json.loads((game_directory / "manifest.json").read_text(encoding="utf-8"))
            entries = json.loads((games / GAME_EVIDENCE_INDEX).read_text(encoding="utf-8"))["entries"]
            resumed.record_unconfirmed("restart-match")
            resumed.close()

        self.assertEqual((next_game_no, retained), (1, 1))
        self.assertEqual(manifest_after_restart["status"], "interrupted")
        self.assertEqual(manifest_after_restart["result"], "result_unconfirmed")
        self.assertEqual(manifest_after_restart["last_stage"], "recovered_after_restart")
        self.assertEqual(manifest_after_resume["status"], "in_progress")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["directory"], game_directory.name)

    def test_fixed_game_evidence_path_rejects_arbitrary_external_batch_layout(self) -> None:
        with TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "BotzoneWorkspace"
            workspace.mkdir()
            recent_dir = workspace / "manual-batch-records"
            recent_dir.mkdir()
            recent_results = recent_dir / "recent-games.json"
            recent_results.write_text("{}", encoding="utf-8")
            games = workspace / "games"
            games.mkdir()
            state = workspace / "runtime" / "v2" / "runs" / "run" / "state"
            state.mkdir(parents=True)
            outside = Path(temporary) / "OtherWorkspace"
            outside.mkdir()
            outside_recent_dir = outside / "manual-batch-records"
            outside_recent_dir.mkdir()
            outside_recent = outside_recent_dir / "recent-games.json"
            outside_recent.write_text("{}", encoding="utf-8")
            outside_games = outside / "games"
            outside_games.mkdir()
            with patch("integrations.botzone.manual_batch.DEFAULT_WORKSPACE_ROOT", workspace):
                valid = _manual_game_evidence_path(
                    str(games), agent="deepseek", continuous=True,
                    recent_results_file=recent_results, state_directory=state,
                    audit_file=None, history_file=None, game_results_file=None,
                )
                with self.assertRaises(ValueError):
                    _manual_game_evidence_path(
                        str(outside_games), agent="deepseek", continuous=True,
                        recent_results_file=outside_recent, state_directory=state,
                        audit_file=None, history_file=None, game_results_file=None,
                    )

        self.assertEqual(valid, games.resolve())

    def test_unknown_or_corrupt_entries_stop_rotation_without_deleting_them(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            games = root / "games"
            prepare_game_evidence(games, 1)
            recorder = ManualGameEvidenceRecorder(games)
            recorder.begin_game("first", own_hand=(1,), player_id=0, global_state=GlobalState("2", 0, None, None))
            recorder.record_finished("first", "local_team_win", platform_finished=True)
            first = next(path for path in games.iterdir() if path.is_dir())
            unknown = games / "keep-me.txt"
            unknown.write_bytes(b"unknown evidence")
            blocked = ManualGameEvidenceRecorder(games)
            index_before = (games / GAME_EVIDENCE_INDEX).read_bytes()
            first_before = (first / "manifest.json").read_bytes()
            blocked.begin_game("second", own_hand=(2,), player_id=1, global_state=GlobalState("2", 0, None, None))
            index_after = (games / GAME_EVIDENCE_INDEX).read_bytes()
            unknown_after = unknown.read_bytes()
            first_after = (first / "manifest.json").read_bytes()

        self.assertTrue(blocked.failed)
        self.assertEqual(blocked.error_category, "evidence_unknown_entry")
        self.assertEqual(unknown_after, b"unknown evidence")
        self.assertEqual(first_after, first_before)
        self.assertEqual(index_after, index_before)

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            games = root / "games"
            prepare_game_evidence(games, 1)
            recorder = ManualGameEvidenceRecorder(games)
            recorder.begin_game("first", own_hand=(1,), player_id=0, global_state=GlobalState("2", 0, None, None))
            recorder.record_finished("first", "local_team_win", platform_finished=True)
            first = next(path for path in games.iterdir() if path.is_dir())
            manifest = first / "manifest.json"
            manifest.write_text("{}", encoding="utf-8")
            with self.assertRaises(GameEvidenceError) as raised:
                prepare_game_evidence(games, 1)
            self.assertEqual(raised.exception.category, "evidence_schema_invalid")
            self.assertEqual(manifest.read_text(encoding="utf-8"), "{}")

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            games = root / "games"
            prepare_game_evidence(games, 1)
            recorder = ManualGameEvidenceRecorder(games)
            recorder.begin_game("first", own_hand=(1,), player_id=0, global_state=GlobalState("2", 0, None, None))
            recorder.record_finished("first", "local_team_win", platform_finished=True)
            game_directory = next(path for path in games.iterdir() if path.is_dir())
            index_path = games / GAME_EVIDENCE_INDEX
            index = json.loads(index_path.read_text(encoding="utf-8"))
            index["entries"][0]["status"] = {"unexpected": "shape"}
            index_path.write_text(json.dumps(index), encoding="utf-8")
            with self.assertRaises(GameEvidenceError) as raised:
                prepare_game_evidence(games, 1)
            directory_still_present = game_directory.is_dir()

        self.assertEqual(raised.exception.category, "evidence_schema_invalid")
        self.assertTrue(directory_still_present)

        with TemporaryDirectory() as temporary:
            games = Path(temporary) / "games"
            prepare_game_evidence(games, 2)
            recorder = ManualGameEvidenceRecorder(games)
            for match in ("first", "second"):
                recorder.begin_game(
                    match, own_hand=(1,), player_id=0,
                    global_state=GlobalState("2", 0, None, None),
                )
                recorder.record_finished(match, "local_team_win", platform_finished=True)
            index_path = games / GAME_EVIDENCE_INDEX
            index = json.loads(index_path.read_text(encoding="utf-8"))
            game_directories = [games / entry["directory"] for entry in index["entries"]]
            manifests_before = [path.joinpath("manifest.json").read_bytes() for path in game_directories]
            index["capacity"] = 1
            index["rotation_pending"] = index["entries"][1]["game_no"]
            index_path.write_text(json.dumps(index), encoding="utf-8")
            with self.assertRaises(GameEvidenceError) as raised:
                prepare_game_evidence(games, 1)
            directories_after = [path.is_dir() for path in game_directories]
            manifests_after = [path.joinpath("manifest.json").read_bytes() for path in game_directories]

        self.assertEqual(raised.exception.category, "evidence_schema_invalid")
        self.assertEqual(directories_after, [True, True])
        self.assertEqual(manifests_after, manifests_before)

    def test_managed_links_are_rejected_and_targets_are_left_untouched(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            games = root / "games"
            prepare_game_evidence(games, 10)
            target = root / "outside.bin"
            target.write_bytes(b"outside")
            link = games / "linked.bin"
            try:
                os.symlink(target, link)
            except (OSError, NotImplementedError):
                self.skipTest("symbolic links are unavailable in this environment")
            with self.assertRaises(GameEvidenceError) as raised:
                prepare_game_evidence(games, 10)
            after = target.read_bytes()

        self.assertEqual(raised.exception.category, "evidence_link_rejected")
        self.assertEqual(after, b"outside")

    def test_write_failure_is_fixed_low_sensitivity_and_never_escapes_recorder(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            games = root / "games"
            prepare_game_evidence(games, 10)
            recorder = ManualGameEvidenceRecorder(games)
            recorder.begin_game("private-match", own_hand=(1,), player_id=0, global_state=GlobalState("2", 0, None, None))
            decision_no = recorder.begin_decision("private-match")
            game_directory = next(path for path in games.iterdir() if path.is_dir())
            with patch.object(
                ManualGameEvidenceRecorder,
                "_event",
                side_effect=GameEvidenceError("evidence_write_failed"),
            ):
                recorder.record_agent_event("private-match", decision_no, "model_complete", {
                    "outcome": "success", "selected_action_id": 1,
                    "reason": "synthetic-short", "reason_truncated": False})
            manifest = json.loads((game_directory / "manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(recorder.failed)
            self.assertEqual(recorder.error_category, "evidence_write_failed")
            self.assertNotIn("private-match", str(recorder.error_category))
            self.assertTrue(manifest["evidence_incomplete"])
            self.assertEqual(manifest["error_category"], "evidence_write_failed")

    def test_explicit_limit_marks_pending_action_unconfirmed_without_stopping_after_capacity(self) -> None:
        with TemporaryDirectory() as temporary:
            games = Path(temporary) / "games"
            prepare_game_evidence(games, 1)
            recorder = ManualGameEvidenceRecorder(games)
            recorder.begin_game("limited-match", own_hand=(1,), player_id=0,
                                global_state=GlobalState("2", 0, None, None))
            recorder.close("cycle_limit_unfinished")
            game_directory = next(path for path in games.iterdir() if path.is_dir())
            manifest = json.loads((game_directory / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["status"], "stopped_at_limit")
        self.assertEqual(manifest["result"], "result_unconfirmed")
        self.assertEqual(manifest["last_stage"], "stopped_at_limit")

    def test_timeout_fallback_without_request_and_pending_header_remain_unconfirmed_on_stop(self) -> None:
        with TemporaryDirectory() as temporary:
            games = Path(temporary) / "games"
            prepare_game_evidence(games, 10)
            recorder = ManualGameEvidenceRecorder(games)
            recorder.begin_game("stop-match", own_hand=(1, 2), player_id=0,
                                global_state=GlobalState("2", 0, None, None))
            decision_no = recorder.begin_decision("stop-match")
            assert decision_no is not None
            sink = recorder.agent_sink("stop-match", decision_no)
            sink("model_enter", {"outcome": "started"})
            sink("model_complete", {"outcome": "timeout"})
            trace = {
                "observation": {"my_info": {"hand_cards": ["3S", "4S"]}},
                "legal_actions": [{"action_id": 1, "carrier_cards": ["3S"]}],
                "selected_action_id": 1,
                "selected_action": {"action_id": 1, "carrier_cards": ["3S"]},
                "decision_source": "deepseek_rule_fallback",
            }

            class _Trace:
                def to_json(self):
                    return trace

            recorder.record_action_pending("stop-match", _Trace())
            recorder.close("interrupted")
            game_dir = next(path for path in games.iterdir() if path.is_dir())
            entry = json.loads((game_dir / "manifest.json").read_text(encoding="utf-8"))
            events = [json.loads(line) for line in (game_dir / "timeline.jsonl").read_text(encoding="utf-8").splitlines()]
            request_files = list((game_dir / "requests").glob("*.json"))

        self.assertEqual(entry["status"], "interrupted")
        self.assertEqual(entry["result"], "result_unconfirmed")
        self.assertEqual(entry["last_stage"], "interrupted")
        self.assertEqual([event["event"] for event in events].count("model_enter"), 1)
        self.assertTrue(any(event["event"] == "model_complete" and event["data"]["outcome"] == "timeout" for event in events))
        self.assertFalse(any(event["event"] == "ack_confirmed" for event in events))
        self.assertEqual(request_files, [])

    def test_public_echo_and_ack_confirmation_are_separate_from_later_pending_action(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            games = root / "games"
            prepare_game_evidence(games, 10)
            evidence = ManualGameEvidenceRecorder(games)
            match = "observed-ack-match"

            class _Transport:
                def __init__(self) -> None:
                    self.call = 0
                    self.first_response: list[list[int]] | None = None

                def poll(self, headers: object) -> bytes:
                    self.call += 1
                    values = list(dict(headers).values())
                    if self.call == 1:
                        return f"1 0\n{match}\n{_deal()}".encode()
                    if self.call == 2:
                        return f"1 0\n{match}\n{_play()}".encode()
                    if self.call == 3:
                        self.assert_has_header(values)
                        envelope = json.loads(values[0].decode("utf-8"))
                        self.first_response = envelope["response"]
                        return f"1 0\n{match}\n{_play_after_action(self.first_response)}".encode()
                    return b"0 0\n"

                @staticmethod
                def assert_has_header(values: list[bytes]) -> None:
                    if not values:
                        raise AssertionError("expected pending play header")

            state = SessionStore(root / "state", decision_trace_enabled=True)
            handler = NoTributeRuleBasedHandler(
                agent_mode="rule", decision_trace_enabled=True, game_evidence_recorder=evidence,
            )
            transport = _Transport()
            connector = MockConnector(state, transport, handler, game_evidence_recorder=evidence)
            connector.cycle()
            connector.cycle()
            connector.cycle()
            pending_state = state.load(match)
            connector.close_game_evidence("interrupted")
            game_dir = next(path for path in games.iterdir() if path.is_dir())
            observations = [json.loads(line)["data"] for line in (game_dir / "observations.jsonl").read_text(encoding="utf-8").splitlines()]
            decisions = [json.loads(line)["data"] for line in (game_dir / "decisions.jsonl").read_text(encoding="utf-8").splitlines()]
            events = [json.loads(line) for line in (game_dir / "timeline.jsonl").read_text(encoding="utf-8").splitlines()]

        self.assertIsNotNone(pending_state)
        assert pending_state is not None
        self.assertIsNotNone(pending_state.pending_response)
        self.assertEqual(len(decisions), 2)
        self.assertEqual(len(observations[-1]["observed_history"]), 1)
        self.assertEqual(
            observations[-1]["observed_history"][0]["response"],
            transport.first_response,
        )
        first_action_ids = set(transport.first_response[0])
        second_carrier_ids = set(pending_state.pending_effect.action)
        self.assertFalse(first_action_ids & second_carrier_ids)
        acknowledgements = [
            event for event in events
            if event["event"] == "ack_confirmed" and event["data"].get("selected_action_id") is not None
        ]
        pending_headers = [event for event in events if event["event"] == "header_pending"]
        self.assertEqual(len(acknowledgements), 1)
        self.assertEqual(len(pending_headers), 2)

    def test_fake_deepseek_transport_body_is_saved_byte_exact_with_candidate_metadata(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            games = root / "games"
            prepare_game_evidence(games, 10)
            recorder = ManualGameEvidenceRecorder(games)
            recorder.begin_game("fake-model-match", own_hand=(1, 2), player_id=0,
                                global_state=GlobalState("2", 0, None, None))
            decision_no = recorder.begin_decision("fake-model-match")
            assert decision_no is not None
            sink = recorder.agent_sink("fake-model-match", decision_no)
            received: list[bytes] = []
            model_output = "test-only-free-form-model-response"

            def fake_transport(request, _timeout: float) -> str:
                received.append(request.data)
                response_content = json.dumps({"action_id": 1, "reason": model_output}, separators=(",", ":"))
                delta = json.dumps({"choices": [{"delta": {"content": response_content}}]}, separators=(",", ":"))
                return f"data: {delta}\ndata: [DONE]\n"

            actions = [
                {"action_id": 1, "declared_pattern": "single", "declared_cards": ["3"],
                 "carrier_cards": ["3S"], "wildcard_count": 0, "wildcard_info": [], "display_text": "single:3"},
                {"action_id": 2, "declared_pattern": "single", "declared_cards": ["4"],
                 "carrier_cards": ["4S"], "wildcard_count": 0, "wildcard_info": [], "display_text": "single:4"},
            ]
            observation = {
                "my_info": {"player_id": 1, "team": "1&3", "hand_cards": ["3S", "4S"],
                            "hand_count": 2, "remaining_single_card_count": 2},
                "current_round": {"step_no": 1, "round_no": 1, "current_player_id": 1,
                                  "current_level_rank": "2", "constraint": "free", "table_action": None},
                "other_players": [
                    {"player_id": 2, "team": "2&4", "hand_count": 5, "finished": False, "finish_rank": None},
                    {"player_id": 3, "team": "1&3", "hand_count": 5, "finished": False, "finish_rank": None},
                    {"player_id": 4, "team": "2&4", "hand_count": 5, "finished": False, "finish_rank": None},
                ],
                "history": {"actions": [], "finish_order": []},
            }
            client = DeepSeekClient("fake-api-key-never-persist", "https://offline.invalid", "deepseek-flash",
                                    max_retries=0, transport=fake_transport)
            suggestion = client.suggest_action_id(
                observation=observation,
                legal_actions=actions,
                prompt_actions=actions,
                request_evidence_observer=lambda body, metadata: recorder.record_agent_event(
                    "fake-model-match", decision_no, "request_prepared", {"body": body, "metadata": metadata}
                ),
            )
            recorder.record_agent_event("fake-model-match", decision_no, "model_complete", {"outcome": "success"})
            recorder.close("interrupted")
            game_dir = next(path for path in games.iterdir() if path.is_dir())
            request_path = next((game_dir / "requests").glob("request_*.json"))
            saved_body = request_path.read_bytes()
            metadata = json.loads(request_path.with_suffix(".meta.json").read_text(encoding="utf-8"))
            all_bytes = b"".join(path.read_bytes() for path in games.rglob("*") if path.is_file())

        self.assertEqual(suggestion.action_id, 1)
        self.assertEqual(len(received), 1)
        self.assertEqual(saved_body, received[0])
        self.assertEqual(metadata["data"]["sha256"], hashlib.sha256(received[0]).hexdigest())
        self.assertEqual(metadata["data"]["candidate_action_ids"], [1, 2])
        self.assertIn(b"deepseek-flash", saved_body)
        self.assertNotIn(b"fake-api-key-never-persist", all_bytes)
        self.assertNotIn(b"offline.invalid", all_bytes)
        self.assertNotIn(model_output.encode("utf-8"), all_bytes)


if __name__ == "__main__":
    unittest.main()
