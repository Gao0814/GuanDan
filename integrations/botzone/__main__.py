"""Explicit foreground entry point for a manually configured local-AI URL."""

from __future__ import annotations

import argparse
from collections.abc import Mapping

from .agent_runtime import prepare_agent_factory
from .http_transport import LocalAIHttpTransport
from .runner import build_foreground_runner, exit_code_for, write_audit
from .runtime_config import RuntimeConfigError, load_runtime_config, preflight_state_directory


_RUNTIME_PREFLIGHT_OUTPUTS = {
    "missing_configuration": "preflight_runtime_config_missing",
    "invalid_configuration": "preflight_runtime_config_url_invalid",
    "invalid_timeout": "preflight_runtime_config_timeout_invalid",
    "invalid_response_limit": "preflight_runtime_config_response_limit_invalid",
    "invalid_failure_limit": "preflight_runtime_config_failure_limit_invalid",
    "invalid_backoff": "preflight_runtime_config_backoff_invalid",
}


def _configuration_output(*, preflight_only: bool, stage: str, error: BaseException) -> str:
    """Return a fixed public category without exposing exception text."""

    if not preflight_only:
        return "configuration_error"
    if stage == "runtime_config" and isinstance(error, RuntimeConfigError):
        return _RUNTIME_PREFLIGHT_OUTPUTS.get(error.category, "preflight_configuration_error")
    if stage == "state_preflight" and isinstance(error, RuntimeConfigError):
        if error.category == "invalid_state_directory":
            return "preflight_state_directory_invalid"
        if error.category == "state_preflight_failed":
            return "preflight_state_operation_failed"
    if stage == "agent_composition":
        return "preflight_agent_composition_failed"
    return "preflight_configuration_error"


def main(argv: list[str] | None = None, *, environ: Mapping[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m integrations.botzone",
        description="Exit codes: 0 finished/preflight, 2 configuration, 4 transport, 5 protocol, 6 limit, 130 interrupt.",
    )
    parser.add_argument("--url")
    parser.add_argument("--state-dir")
    parser.add_argument("--timeout-seconds", default=30)
    parser.add_argument("--agent", choices=("rule", "deepseek"), default="rule")
    parser.add_argument("--max-cycles", type=int, default=100)
    parser.add_argument("--max-wall-seconds", type=int, default=600)
    parser.add_argument("--stop-after-finished", type=int, default=1)
    parser.add_argument("--audit-file")
    parser.add_argument("--preflight-only", action="store_true", help="validate configuration and storage without polling")
    arguments = parser.parse_args(argv)
    stage = "runtime_config"
    try:
        config = load_runtime_config(
            local_ai_url=arguments.url,
            state_directory=arguments.state_dir,
            timeout_seconds=arguments.timeout_seconds,
            environ=environ,
        )
        stage = "state_preflight"
        preflight_state_directory(config)
        stage = "agent_composition"
        prepared_agent_factory = prepare_agent_factory(arguments.agent)
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
            agent_mode=arguments.agent,
            prepared_agent_factory=prepared_agent_factory,
        )
        summary = runner.run(
            max_cycles=arguments.max_cycles,
            max_wall_seconds=arguments.max_wall_seconds,
            stop_after_finished=arguments.stop_after_finished,
        )
        exit_code = exit_code_for(summary)
        if arguments.audit_file is not None:
            write_audit(arguments.audit_file, summary, exit_code)
    except (RuntimeConfigError, ValueError) as error:
        print(_configuration_output(preflight_only=arguments.preflight_only, stage=stage, error=error))
        return 2
    print(f"connector_finished cycles={summary.cycles} finished={summary.finished_seen} exit={exit_code}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
