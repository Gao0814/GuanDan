"""Explicit foreground entry point for a manually configured local-AI URL."""

from __future__ import annotations

import argparse
from collections.abc import Mapping

from .http_transport import LocalAIHttpTransport
from .runner import build_foreground_runner, exit_code_for, write_audit
from .runtime_config import RuntimeConfigError, load_runtime_config, preflight_state_directory


def main(argv: list[str] | None = None, *, environ: Mapping[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m integrations.botzone",
        description="Exit codes: 0 finished/preflight, 2 configuration, 4 transport, 5 protocol, 6 limit, 130 interrupt.",
    )
    parser.add_argument("--url")
    parser.add_argument("--state-dir")
    parser.add_argument("--timeout-seconds", default=30)
    parser.add_argument("--max-cycles", type=int, default=100)
    parser.add_argument("--max-wall-seconds", type=int, default=600)
    parser.add_argument("--stop-after-finished", type=int, default=1)
    parser.add_argument("--audit-file")
    parser.add_argument("--preflight-only", action="store_true", help="validate configuration and storage without polling")
    arguments = parser.parse_args(argv)
    try:
        config = load_runtime_config(
            local_ai_url=arguments.url,
            state_directory=arguments.state_dir,
            timeout_seconds=arguments.timeout_seconds,
            environ=environ,
        )
        preflight_state_directory(config)
        if arguments.preflight_only:
            print("preflight_ready")
            return 0
        runner = build_foreground_runner(
            config,
            LocalAIHttpTransport(
                config.local_ai_url,
                timeout_seconds=config.timeout_seconds,
                max_response_bytes=config.max_response_bytes,
            ),
        )
        summary = runner.run(
            max_cycles=arguments.max_cycles,
            max_wall_seconds=arguments.max_wall_seconds,
            stop_after_finished=arguments.stop_after_finished,
        )
        exit_code = exit_code_for(summary)
        if arguments.audit_file is not None:
            write_audit(arguments.audit_file, summary, exit_code)
    except (RuntimeConfigError, ValueError):
        print("configuration_error")
        return 2
    print(f"connector_finished cycles={summary.cycles} finished={summary.finished_seen} exit={exit_code}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
