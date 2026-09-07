from __future__ import annotations

import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from integrations.botzone.connector import MockConnector
from integrations.botzone.history import ConnectorObservedHistory, _pattern_label
from integrations.botzone.models import ActionClaim, DealRequest, GlobalState, HistoryEntry
from integrations.botzone.poll import FinishedRow
from integrations.botzone.session import HandlerResult, PlayEffect, SessionRecord, SessionStore


def _record(*, history: tuple[HistoryEntry, ...], own_hand: tuple[int, ...], local: int = 0) -> SessionRecord:
    return SessionRecord(
        match_id="synthetic-match",
        request_digest="synthetic",
        stage="play",
        global_state=GlobalState("2", 0, None, None, False),
        own_hand=own_hand,
        local_player_id=local,
        history=history,
        latest_window=history[-4:],
        pending_response=None,
        pending_effect=None,
        delivery_state="idle",
        handler_completed=True,
        cached_response=None,
        cached_response_digest=None,
    )


class _Transport:
    def __init__(self, polls: list[bytes]) -> None:
        self.polls = polls
        self.headers: list[dict[str, bytes]] = []

    def poll(self, headers: object) -> bytes:
        self.headers.append(dict(headers))
        return self.polls.pop(0)


def _global() -> dict[str, object]:
    return {"level": "2", "tribute": 0, "first": None, "last": None, "resist": False, "tribute_cards": {}, "return_cards": {}}


def _direct(stage: dict[str, object]) -> bytes:
    return ("1 0\nsynthetic-match\n" + json.dumps(stage, separators=(",", ":"))).encode()


def _finished() -> bytes:
    return b"0 1\nsynthetic-match 0 4 1 0 1 0"


class BotzoneHistoryTests(unittest.TestCase):
    def test_renderer_shows_public_actions_chinese_cards_wildcard_and_unknown_hands(self) -> None:
        history = (
            HistoryEntry(0, ActionClaim((0,), (0,))),
            HistoryEntry(1, ActionClaim((4,), (24,))),  # H2 declares H7 via wildcard claim.
            HistoryEntry(2, ActionClaim.pass_action()),
            HistoryEntry(3, ActionClaim((52,), (52,))),
            HistoryEntry(0, ActionClaim.pass_action()),
            HistoryEntry(1, ActionClaim.pass_action()),
            HistoryEntry(2, ActionClaim.pass_action()),
            HistoryEntry(3, ActionClaim((53,), (53,))),
        )
        with TemporaryDirectory() as root:
            path = Path(root) / "history.txt"
            recorder = ConnectorObservedHistory(path)
            recorder.update(_record(history=history, own_hand=tuple(range(1, 27))))
            text = path.read_text(encoding="utf-8")
        self.assertIn("==== Connector Observed History ====", text)
        self.assertIn("玩家1手牌：", text)
        self.assertIn("H2（红桃2）", text)
        self.assertIn("第1轮 第2步 玩家2：单张 7", text)
        self.assertIn("声明牌：7", text)
        self.assertIn("载体牌：H2（红桃2）", text)
        self.assertIn("第1轮 第3步 玩家3：pass", text)
        self.assertIn("SJ（小王）", text)
        self.assertIn("玩家2手牌：未知（剩余26张）", text)
        self.assertNotIn("synthetic-match", text)
        for forbidden in ("request_digest", "run_token", "https://", "Cookie", "response\":", "reasoning"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)

    def test_pending_local_response_is_not_written_as_observed_action_and_replay_is_idempotent(self) -> None:
        deal = {"stage": "deal", "deliver": list(range(27)), "your_id": 0, "global": {"level": "2", "tribute": 0, "first": None, "last": None}}
        play = {"stage": "play", "history": [[], [], [], []], "done": [], "pass_on": -1, "global": _global()}
        observed = {"stage": "play", "history": [[], [], {"player": 0, "response": [[0], [0]]}, {"player": 1, "response": [[], []]}], "done": [], "pass_on": -1, "global": _global()}
        with TemporaryDirectory() as root:
            path = Path(root) / "history.txt"
            transport = _Transport([_direct(deal), _direct(play), _direct(observed), _direct(observed)])
            calls = 0

            def handler(context: object) -> HandlerResult:
                nonlocal calls
                calls += 1
                if calls == 1:
                    return HandlerResult(b"[]")
                card = 0 if calls == 2 else 1
                return HandlerResult(json.dumps([[card], [card]]).encode(), PlayEffect((card,), (card,)))

            recorder = ConnectorObservedHistory(path)
            connector = MockConnector(SessionStore(root), transport, handler, history_recorder=recorder)
            connector.cycle()
            connector.cycle()
            pending_text = path.read_text(encoding="utf-8")
            self.assertNotIn("第1轮 第1步", pending_text)
            connector.cycle()
            connector.cycle()
            text = path.read_text(encoding="utf-8")
            self.assertFalse(recorder.failed)
        self.assertEqual(calls, 3)
        self.assertEqual(text.count("第1轮 第1步 玩家1：单张 A"), 1)
        self.assertEqual(text.count("第1轮 第2步 玩家2：pass"), 1)

    def test_complete_terminal_fixture_backfills_only_provable_hands_and_ranks(self) -> None:
        history = tuple(
            HistoryEntry(player, ActionClaim((card_id,), (card_id,)))
            for player in range(3)
            for card_id in range(player * 27, (player + 1) * 27)
        )
        with TemporaryDirectory() as root:
            path = Path(root) / "history.txt"
            ConnectorObservedHistory(path).finish(_record(history=history, own_hand=()), FinishedRow("synthetic-match", 0, 4, (1, 0, 1, 0)))
            text = path.read_text(encoding="utf-8")
        self.assertIn("玩家2手牌：推导手牌", text)
        self.assertIn("玩家4手牌：推导手牌", text)
        self.assertIn("本队结果：胜", text)
        self.assertIn("头游：玩家1", text)
        self.assertIn("二游：玩家2", text)
        self.assertIn("三游：玩家3", text)
        self.assertIn("四游：玩家4", text)
        self.assertIn("==== 对局结束时的手牌 ====", text)
        self.assertIn("history_completeness: terminal_history_complete", text)

    def test_incomplete_terminal_never_claims_hidden_hands_or_ranks(self) -> None:
        history = (HistoryEntry(0, ActionClaim((0,), (0,))),)
        with TemporaryDirectory() as root:
            path = Path(root) / "history.txt"
            ConnectorObservedHistory(path).finish(_record(history=history, own_hand=tuple(range(1, 27))), FinishedRow("synthetic-match", 0, 4, (0, 0, 1, 1)))
            text = path.read_text(encoding="utf-8")
        self.assertIn("玩家2手牌：未知（剩余27张）", text)
        self.assertIn("头游：未知", text)
        self.assertIn("轮次说明：第N轮仅表示 connector 按已观察公开动作划分的第N个牌权段，不保证等于裁判完整终局轮次。", text)
        self.assertNotIn("==== 第1轮结束后的手牌 ====", text)
        self.assertIn("==== 最后一次观测后的手牌（该牌权段可能尚未结束） ====", text)
        self.assertIn("说明：平台已通知对局结束；最后一次观测后至终局的公开动作可能未被 connector 观察到。", text)
        self.assertIn("history_completeness: terminal_tail_may_be_unobserved", text)

    def test_next_observed_segment_proves_only_the_prior_segment_ended(self) -> None:
        history = (
            HistoryEntry(0, ActionClaim((0,), (0,))),
            HistoryEntry(1, ActionClaim.pass_action()),
            HistoryEntry(2, ActionClaim.pass_action()),
            HistoryEntry(3, ActionClaim.pass_action()),
            HistoryEntry(0, ActionClaim((4,), (4,))),
        )
        with TemporaryDirectory() as root:
            path = Path(root) / "history.txt"
            ConnectorObservedHistory(path).update(_record(history=history, own_hand=tuple(range(1, 27))))
            text = path.read_text(encoding="utf-8")
        self.assertIn("==== 第1轮结束后的手牌 ====", text)
        self.assertNotIn("==== 第2轮结束后的手牌 ====", text)

    def test_incomplete_terminal_after_local_exhaustion_mentions_unobserved_tail(self) -> None:
        history = tuple(HistoryEntry(0, ActionClaim((card_id,), (card_id,))) for card_id in range(27))
        with TemporaryDirectory() as root:
            path = Path(root) / "history.txt"
            ConnectorObservedHistory(path).finish(_record(history=history, own_hand=()), FinishedRow("synthetic-match", 0, 4, (0, 0, 1, 1)))
            text = path.read_text(encoding="utf-8")
        self.assertIn("==== 最后一次观测后的手牌（该牌权段可能尚未结束） ====", text)
        self.assertIn("说明：平台已通知对局结束；本家出完后至终局的公开动作可能未被 connector 观察到。", text)
        self.assertIn("history_completeness: terminal_tail_may_be_unobserved", text)

    def test_write_failure_is_sticky_and_cannot_break_delivery(self) -> None:
        with TemporaryDirectory() as root:
            recorder = ConnectorObservedHistory(Path(root) / "missing" / "history.txt")
            recorder.update(_record(history=(), own_hand=tuple(range(27))))
            self.assertTrue(recorder.failed)
            self.assertFalse((Path(root) / "missing" / "history.txt").exists())

            deal = {"stage": "deal", "deliver": list(range(27)), "your_id": 0, "global": {"level": "2", "tribute": 0, "first": None, "last": None}}
            connector = MockConnector(
                SessionStore(Path(root) / "state"),
                _Transport([_direct(deal)]),
                lambda _: HandlerResult(b"[]"),
                history_recorder=ConnectorObservedHistory(Path(root) / "missing" / "history.txt"),
            )
            self.assertEqual(connector.cycle().responses_prepared, 1)

    def test_atomic_replace_failure_leaves_no_temporary_history_file(self) -> None:
        with TemporaryDirectory() as root:
            path = Path(root) / "history.txt"
            recorder = ConnectorObservedHistory(path)
            with patch("integrations.botzone.history.os.replace", side_effect=OSError("synthetic")):
                recorder.update(_record(history=(), own_hand=tuple(range(27))))
            self.assertTrue(recorder.failed)
            self.assertEqual(list(Path(root).iterdir()), [])

    def test_bot_envelope_replay_writes_each_observed_entry_once(self) -> None:
        deal = {"stage": "deal", "deliver": list(range(27)), "your_id": 0, "global": {"level": "2", "tribute": 0, "first": None, "last": None}}
        empty = {"stage": "play", "history": [[], [], [], []], "done": [], "pass_on": -1, "global": _global()}
        observed = {"stage": "play", "history": [[], [], [], {"player": 0, "response": [[0], [0]]}], "done": [], "pass_on": -1, "global": _global()}
        envelope = json.dumps({"requests": [deal, empty, observed], "responses": [[], [[0], [0]]]}, separators=(",", ":"))
        with TemporaryDirectory() as root:
            path = Path(root) / "history.txt"
            connector = MockConnector(
                SessionStore(root),
                _Transport([(f"1 0\nsynthetic-match\n{envelope}").encode(), (f"1 0\nsynthetic-match\n{envelope}").encode()]),
                lambda context: HandlerResult(b"[[1],[1]]", PlayEffect((1,))),
                history_recorder=ConnectorObservedHistory(path),
            )
            connector.cycle()
            connector.cycle()
            text = path.read_text(encoding="utf-8")
        self.assertEqual(text.count("第1轮 第1步 玩家1：单张 A"), 1)

    def test_acknowledged_last_action_is_rendered_before_finished_tombstone(self) -> None:
        deal = {"stage": "deal", "deliver": list(range(27)), "your_id": 0, "global": {"level": "2", "tribute": 0, "first": None, "last": None}}
        play = {"stage": "play", "history": [[], [], [], []], "done": [], "pass_on": -1, "global": _global()}
        with TemporaryDirectory() as root:
            path = Path(root) / "history.txt"
            transport = _Transport([_direct(deal), _direct(play), _finished()])

            def handler(context: object) -> HandlerResult:
                if isinstance(context.request, DealRequest):
                    return HandlerResult(b"[]")
                return HandlerResult(b"[[0],[0]]", PlayEffect((0,), (0,)))

            connector = MockConnector(SessionStore(root), transport, handler, history_recorder=ConnectorObservedHistory(path))
            connector.cycle()
            connector.cycle()
            final_cycle = connector.cycle()
            text = path.read_text(encoding="utf-8")
        self.assertEqual(final_cycle.finished_qualified, 1)
        self.assertEqual(text.count("第1轮 第1步 玩家1：单张 A"), 1)
        self.assertIn("history_completeness: terminal_tail_may_be_unobserved", text)

    def test_second_match_marks_history_failed_without_overwriting_first_file(self) -> None:
        first = {"stage": "deal", "deliver": list(range(27)), "your_id": 0, "global": {"level": "2", "tribute": 0, "first": None, "last": None}}
        second = {"stage": "deal", "deliver": list(range(27, 54)), "your_id": 1, "global": {"level": "2", "tribute": 0, "first": None, "last": None}}
        with TemporaryDirectory() as root:
            path = Path(root) / "history.txt"
            recorder = ConnectorObservedHistory(path)
            connector = MockConnector(
                SessionStore(root),
                _Transport([(f"2 0\nfirst\n{json.dumps(first, separators=(',', ':'))}\nsecond\n{json.dumps(second, separators=(',', ':'))}").encode()]),
                lambda _: HandlerResult(b"[]"),
                history_recorder=recorder,
            )
            self.assertEqual(connector.cycle().responses_prepared, 2)
            text = path.read_text(encoding="utf-8")
        self.assertEqual(recorder.status, "failed")
        self.assertIn("HA（红桃A）", text)
        self.assertNotIn("H8（红桃8）", text)

    def test_pattern_labels_use_adapter_rule_truth(self) -> None:
        def entry(ids: tuple[int, ...]) -> HistoryEntry:
            return HistoryEntry(0, ActionClaim(ids, ids))

        cases = (
            ((0, 4, 8, 12, 16), "9", "同花顺"),
            ((0, 5, 10, 15, 16), "9", "顺子"),
            ((4, 8, 12, 16, 20), "2", "同花顺"),
            ((24, 25), "9", "对子"),
            ((24, 25, 26, 28, 29), "9", "三带二"),
            ((8, 9, 10, 12, 13, 14), "9", "钢板"),
            ((8, 9, 12, 13, 16, 17), "9", "连对"),
            ((0, 1, 2, 3), "9", "炸弹"),
            ((52, 53, 106, 107), "9", "天王炸"),
        )
        for ids, level, expected in cases:
            with self.subTest(expected=expected):
                self.assertEqual(_pattern_label(entry(ids), level), expected)

    def test_cli_history_argument_reaches_actual_runner_composition(self) -> None:
        from integrations.botzone import __main__ as entry

        with TemporaryDirectory() as root:
            received: dict[str, object] = {}
            state = Path(root) / "state"

            def fail_after_capture(*_: object, **kwargs: object) -> object:
                received.update(kwargs)
                raise ValueError("synthetic")

            with patch.object(entry, "build_foreground_runner", side_effect=fail_after_capture):
                self.assertEqual(entry.main(["--url", "https://example.invalid", "--state-dir", str(state), "--history-file", str(Path(root) / "history.txt")], environ={}), 2)
            self.assertEqual(received["history_file"], Path(root) / "history.txt")

    def test_cli_rejects_a_history_file_inside_the_repository(self) -> None:
        from integrations.botzone import __main__ as entry

        with TemporaryDirectory() as root:
            source_path = Path(__file__).parents[1] / "history.txt"
            self.assertEqual(entry.main(["--url", "https://example.invalid", "--state-dir", root, "--history-file", str(source_path)], environ={}), 2)

    def test_cli_rejects_history_collisions_with_state_or_audit(self) -> None:
        from integrations.botzone import __main__ as entry

        with TemporaryDirectory() as root:
            base = Path(root)
            state = base / "state"
            self.assertEqual(entry.main(["--url", "https://example.invalid", "--state-dir", str(state), "--history-file", str(state / "history.txt")], environ={}), 2)
            self.assertEqual(entry.main(["--url", "https://example.invalid", "--state-dir", str(base / "other-state"), "--audit-file", str(base / "same.txt"), "--history-file", str(base / "same.txt")], environ={}), 2)

    def test_cli_summary_exposes_fixed_history_status(self) -> None:
        from integrations.botzone import __main__ as entry

        class _Runner:
            run_token = None

            def run(self, **_: object) -> object:
                return type("Summary", (), {"cycles": 3, "finished_seen": 1, "history_status": "failed", "stopped": "finished_target", "finished_qualified": 1})()

        with TemporaryDirectory() as root:
            output = StringIO()
            with patch.object(entry, "build_foreground_runner", return_value=_Runner()), redirect_stdout(output):
                self.assertEqual(entry.main(["--url", "https://example.invalid", "--state-dir", str(Path(root) / "state")], environ={}), 0)
        self.assertEqual(output.getvalue(), "connector_finished cycles=3 finished=1 history=failed exit=0\n")


if __name__ == "__main__":
    unittest.main()
