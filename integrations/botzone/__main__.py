"""Explicit foreground entry point for a manually configured local-AI URL."""

from __future__ import annotations

import argparse
from collections.abc import Mapping

from .http_transport import LocalAIHttpTransport
from .runner import build_foreground_runner
from .runtime_config import RuntimeConfigError, load_runtime_config


def main(argv: list[str] | None = None, *, environ: Mapping[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m integrations.botzone")
    parser.add_argument("--url")
    parser.add_argument("--state-dir")
    parser.add_argument("--timeout-seconds", default=30)
    parser.add_argument("--max-cycles", type=int)
    arguments = parser.parse_args(argv)
    try:
        config = load_runtime_config(
            local_ai_url=arguments.url,
            state_directory=arguments.state_dir,
            timeout_seconds=arguments.timeout_seconds,
            environ=environ,
        )
        runner = build_foreground_runner(
            config,
            LocalAIHttpTransport(
                config.local_ai_url,
                timeout_seconds=config.timeout_seconds,
                max_response_bytes=config.max_response_bytes,
            ),
        )
        summary = runner.run(max_cycles=arguments.max_cycles)
    except RuntimeConfigError:
        print("configuration_error")
        return 2
    print(f"connector_finished cycles={summary.cycles} stopped={summary.stopped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
