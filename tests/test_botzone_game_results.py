from __future__ import annotations

import io
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from integrations.botzone.connector import MockConnector
from integrations.botzone.__main__ import _game_results_path
from integrations.botzone.game_results import (
    GAME_RESULT_SCHEMA,
    GameResultRecorder,
)
from integrations.botzone.models import DealRequest, PlayRequest
from integrations.botzone.manual_batch import run_batch
from integrations.botzone.result_observability import RESULT_CATEGORIES
from integrations.botzone.runner import ForegroundRunner, exit_code_for, write_audit
from integrations.botzone.session import HandlerContext, HandlerResult, PlayEffect, SessionStore
from integrations.botzone.stage_trace import STAGE_TRACE_PREFIX, StageTrace


_TOKEN = "0123456789abcdef0123456789abcdef"


def _deal(player: int) -> dict[str, object]:
    return {
        "stage": "deal",
        "deliver": list(range(player * 27, (player + 1) * 27)),
        "your_id": player,
        "global": {"level": "2", "tribute": 0, "first": None, "last": None},
    }


def _play() -> dict[str, object]:
    return {
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


def _poll(
    requests: tuple[tuple[str, dict[str, object]], ...] = (),
    finished: tuple[tuple[str, int, int, tuple[int, ...]], ...] = (),
) -> bytes:
    lines = [f"{len(requests)} {len(finished)}"]
    for match_id, request in requests:
        lines.extend((match_id, json.dumps(request, separators=(",", ":"))))
    for match_id, local_player, player_count, scores in finished:
        lines.append(" ".join((match_id, str(local_player), str(player_count), *(str(score) for score in scores))))
    return "\n".join(lines).encode("utf-8")


class _Transport:
    def __init__(self, polls: list[bytes]) -> None:
        self.polls = list(polls)
        self.headers: list[dict[str, bytes]] = []

    def poll(self, headers: object) -> bytes:
        self.headers.append(dict(headers))  # type: ignore[arg-type]
        return self.polls.pop(0)


def _handler(context: HandlerContext) -> HandlerResult:
    if isinstance(context.request, DealRequest):
        return HandlerResult(b"[]")
    assert isinstance(context.request, PlayRequest)
    card_id = context.own_hand[0]
    return HandlerResult(
        json.dumps([[card_id], [card_id]], separators=(",", ":")).encode(),
        PlayEffect((card_id,), (card_id,)),
    )


def _rows(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class BotzoneGameResultTests(unittest.TestCase):
    def test_three_confirmed_results_auto_stop_after_target_and_idle_poll_is_not_a_game(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            result_path = root / "game-results.jsonl"
            recorder = GameResultRecorder(result_path)
            deals = tuple((name, _deal(index)) for index, name in enumerate(("a", "b", "c")))
            plays = tuple((name, _play()) for name in ("a", "b", "c"))
            terminals = (
                ("a", 0, 4, (2, 0, 2, 0)),  # local team win
                ("b", 0, 4, (0, 1, 0, 1)),  # local team loss
                ("c", 0, 4, (-2, 1, 0, 1)),  # platform_error
            )
            stream = io.StringIO()
            trace = StageTrace(stream)
            transport = _Transport([_poll(), _poll(deals), _poll(plays), _poll(finished=terminals)])
            connector = MockConnector(
                SessionStore(root / "state"),
                transport,
                _handler,
                game_result_recorder=recorder,
                stage_trace=trace,
            )
            summary = ForegroundRunner(
                connector,
                max_consecutive_failures=2,
                backoff_seconds=0,
                sleep=lambda _seconds: None,
                stage_trace=trace,
            ).run(max_cycles=10, stop_after_finished=3)
            audit_path = root / "audit.json"
            write_audit(audit_path, summary, exit_code_for(summary), run_token=_TOKEN)

            rows = _rows(result_path)
            result_text = result_path.read_text(encoding="utf-8")
            aggregate = json.loads(audit_path.read_text(encoding="utf-8"))
            events = [
                json.loads(line[len(STAGE_TRACE_PREFIX):])
                for line in stream.getvalue().splitlines()
                if line.startswith(STAGE_TRACE_PREFIX)
            ]

        self.assertEqual(summary.stopped, "finished_target")
        self.assertEqual(summary.cycles, 4)
        self.assertEqual(summary.finished_qualified, 3)
        self.assertEqual(summary.headers_sent, 6)
        self.assertEqual((summary.game_results_status, summary.game_results_recorded), ("ok", 3))
        self.assertEqual([row["game_no"] for row in rows], [1, 2, 3])
        self.assertEqual(
            [row["result"] for row in rows],
            ["local_team_win", "local_team_loss", "platform_error"],
        )
        self.assertTrue(all(set(row) == {"game_no", "result", "schema", "version"} for row in rows))
        self.assertTrue(all(row["schema"] == GAME_RESULT_SCHEMA and row["version"] == 1 for row in rows))
        self.assertEqual(dict(aggregate["result_category_counts"]), {
            "local_team_loss": 1,
            "local_team_win": 1,
            "platform_error": 1,
        })
        self.assertEqual(sum(event["stage"] == "response_acknowledged" for event in events), 2)
        first_finished = next(index for index, event in enumerate(events) if event["stage"] == "finished")
        self.assertTrue(any(event["stage"] == "response_acknowledged" for event in events[:first_finished]))
        self.assertNotIn('"match_id"', result_text)
        self.assertNotIn("synthetic", result_text)

    def test_interleaved_matches_and_repeated_terminal_rows_do_not_double_count(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            results = GameResultRecorder(root / "games.jsonl")
            first_finished = (("first-private-id", 0, 4, (2, 0, 2, 0)),)
            second_finished = (("second-private-id", 0, 4, (-2, 1, 0, 1)),)
            polls = [
                _poll((("first-private-id", _deal(0)), ("second-private-id", _deal(1)))),
                _poll((("first-private-id", _play()),)),
                _poll((("second-private-id", _play()),), first_finished),
                _poll(finished=second_finished),
                _poll(finished=first_finished + second_finished),
                _poll(),
            ]
            transport = _Transport(polls)
            summary = ForegroundRunner(
                MockConnector(SessionStore(root / "state"), transport, _handler, game_result_recorder=results),
                max_consecutive_failures=2,
                backoff_seconds=0,
                sleep=lambda _seconds: None,
            ).run(max_cycles=6, stop_after_finished=3)
            rows = _rows(root / "games.jsonl")

        self.assertEqual(summary.finished_seen, 4)
        self.assertEqual(summary.finished_qualified, 2)
        self.assertEqual(summary.game_results_recorded, 2)
        self.assertEqual(summary.game_results_status, "ok")
        self.assertEqual([row["game_no"] for row in rows], [1, 2])
        self.assertEqual([row["result"] for row in rows], ["local_team_win", "platform_error"])
        self.assertEqual(sum(dict(summary.result_category_counts).values()), 2)

    def test_single_runner_continues_through_idle_polls_between_two_finished_games(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            result_path = root / "game-results.jsonl"
            recorder = GameResultRecorder(result_path)
            transport = _Transport(
                [
                    _poll(),
                    _poll((("first-match", _deal(0)),)),
                    _poll((("first-match", _play()),)),
                    _poll(finished=(("first-match", 0, 4, (2, 0, 2, 0)),)),
                    _poll(),
                    _poll((("second-match", _deal(1)),)),
                    _poll((("second-match", _play()),)),
                    _poll(finished=(("second-match", 1, 4, (2, 0, 2, 0)),)),
                ]
            )
            summary = ForegroundRunner(
                MockConnector(SessionStore(root / "state"), transport, _handler, game_result_recorder=recorder),
                max_consecutive_failures=1,
                backoff_seconds=0,
                sleep=lambda _seconds: self.fail("idle polls must keep the same runner active without backoff"),
            ).run(max_cycles=10, stop_after_finished=2)
            results = _rows(result_path)

        self.assertEqual(summary.stopped, "finished_target")
        self.assertEqual(summary.cycles, 8)
        self.assertEqual(summary.finished_qualified, 2)
        self.assertEqual(summary.game_results_recorded, 2)
        self.assertEqual([row["game_no"] for row in results], [1, 2])
        self.assertEqual([row["result"] for row in results], ["local_team_win", "local_team_loss"])

    def test_one_batch_process_runs_the_same_connector_through_idle_and_two_games(self) -> None:
        with TemporaryDirectory() as temporary:
            base = Path(temporary)
            workspace = base / "BotzoneWorkspace"
            workspace.mkdir()
            old_evidence = workspace / "old-evidence.json"
            old_evidence.write_text("keep", encoding="utf-8")
            calls: list[list[str]] = []
            runtime_summaries = []

            def fake_process(argv: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
                calls.append(argv)
                if argv[0] == "powershell.exe":
                    return subprocess.CompletedProcess(argv, 0, "connector_absent\n", "")
                if "--preflight-only" in argv:
                    return subprocess.CompletedProcess(argv, 0, "preflight_ready\n", "")

                def option(name: str) -> str:
                    return argv[argv.index(name) + 1]

                trace = StageTrace(kwargs["stdout"])  # type: ignore[arg-type]
                connector = MockConnector(
                    SessionStore(Path(option("--state-dir"))),
                    _Transport(
                        [
                            _poll(),
                            _poll((("first-match", _deal(0)),)),
                            _poll((("first-match", _play()),)),
                            _poll(finished=(("first-match", 0, 4, (2, 0, 2, 0)),)),
                            _poll(),
                            _poll((("second-match", _deal(1)),)),
                            _poll((("second-match", _play()),)),
                            _poll(finished=(("second-match", 1, 4, (2, 0, 2, 0)),)),
                        ]
                    ),
                    _handler,
                    game_result_recorder=GameResultRecorder(Path(option("--game-results-file"))),
                    stage_trace=trace,
                )
                summary = ForegroundRunner(
                    connector,
                    max_consecutive_failures=1,
                    backoff_seconds=0,
                    sleep=lambda _seconds: self.fail("the idle interval must keep polling without a restart"),
                    agent_mode="deepseek",
                    run_token=option("--run-token"),
                    stage_trace=trace,
                ).run(
                    max_cycles=int(option("--max-cycles")),
                    max_wall_seconds=int(option("--max-wall-seconds")),
                    stop_after_finished=int(option("--stop-after-finished")),
                )
                runtime_summaries.append(summary)
                connector_exit = exit_code_for(summary)
                write_audit(Path(option("--audit-file")), summary, connector_exit, run_token=option("--run-token"))
                kwargs["stdout"].write(  # type: ignore[attr-defined]
                    f"connector_finished cycles={summary.cycles} finished={summary.finished_seen} "
                    f"history=disabled decision_trace=disabled game_results={summary.game_results_status} "
                    f"game_results_recorded={summary.game_results_recorded} exit={connector_exit}\n"
                )
                return subprocess.CompletedProcess(argv, connector_exit, "", "")

            messages: list[str] = []
            outcome = run_batch(
                games=2,
                max_cycles=12,
                max_wall_seconds=60,
                workspace_root=workspace,
                repository_root=base,
                process_runner=fake_process,
                announce=messages.append,
            )
            old_content = old_evidence.read_text(encoding="utf-8")
            results = _rows(outcome.batch_directory / "game-results.jsonl")
            trace_text = (outcome.batch_directory / "streams" / "stdout.txt").read_text(encoding="utf-8")

        self.assertEqual(len(calls), 3)
        self.assertEqual(sum("--preflight-only" not in argv and argv[0] != "powershell.exe" for argv in calls), 1)
        self.assertEqual(len(runtime_summaries), 1)
        self.assertEqual(runtime_summaries[0].cycles, 8)
        self.assertEqual(runtime_summaries[0].stopped, "finished_target")
        self.assertEqual(outcome.category, "target_reached")
        self.assertEqual(outcome.confirmed_finished, 2)
        self.assertEqual([row["game_no"] for row in results], [1, 2])
        self.assertIn("response_acknowledged", trace_text)
        self.assertTrue(any(message.startswith("batch_result category=target_reached exit=0") for message in messages))
        self.assertEqual(old_content, "keep")

    def test_result_write_failure_is_reported_without_changing_acknowledgement(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            results = GameResultRecorder(root / "games.jsonl")
            transport = _Transport(
                [
                    _poll((("match", _deal(0)),)),
                    _poll((("match", _play()),)),
                    _poll(finished=(("match", 0, 4, (2, 0, 2, 0)),)),
                ]
            )
            connector = MockConnector(SessionStore(root / "state"), transport, _handler, game_result_recorder=results)
            with patch.object(GameResultRecorder, "record", side_effect=OSError("private error")):
                summary = ForegroundRunner(
                    connector,
                    max_consecutive_failures=2,
                    backoff_seconds=0,
                    sleep=lambda _seconds: None,
                ).run(max_cycles=3, stop_after_finished=1)
            record = SessionStore(root / "state").load("match")

        self.assertEqual(summary.finished_qualified, 1)
        self.assertEqual(summary.stopped, "finished_target")
        self.assertEqual(summary.game_results_status, "failed")
        self.assertEqual(summary.game_results_recorded, 0)
        self.assertEqual(len(transport.headers[2]), 1)
        self.assertIsNone(record)

    def test_existing_result_path_is_never_overwritten(self) -> None:
        with TemporaryDirectory() as temporary:
            target = Path(temporary) / "games.jsonl"
            target.write_text("old evidence\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "game_results_output_unavailable"):
                GameResultRecorder(target)
            self.assertEqual(target.read_text(encoding="utf-8"), "old evidence\n")

    def test_result_categories_are_low_cardinality(self) -> None:
        self.assertEqual(
            RESULT_CATEGORIES,
            frozenset({"local_team_win", "local_team_loss", "platform_error", "invalid_score_shape"}),
        )

    def test_cli_result_path_requires_fresh_absolute_external_output(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "state"
            state.mkdir()
            result_path = root / "game-results.jsonl"
            self.assertEqual(
                _game_results_path(
                    str(result_path),
                    state_directory=state,
                    audit_file=str(root / "audit.json"),
                    history_file=None,
                    decision_trace_file=None,
                ),
                result_path,
            )
            result_path.write_text("existing", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid_game_results_path"):
                _game_results_path(
                    str(result_path),
                    state_directory=state,
                    audit_file=None,
                    history_file=None,
                    decision_trace_file=None,
                )
            with self.assertRaisesRegex(ValueError, "invalid_game_results_path"):
                _game_results_path(
                    str(state / "games.jsonl"),
                    state_directory=state,
                    audit_file=None,
                    history_file=None,
                    decision_trace_file=None,
                )
            with self.assertRaisesRegex(ValueError, "invalid_game_results_path"):
                _game_results_path(
                    "relative.jsonl",
                    state_directory=state,
                    audit_file=None,
                    history_file=None,
                    decision_trace_file=None,
                )


if __name__ == "__main__":
    unittest.main()
