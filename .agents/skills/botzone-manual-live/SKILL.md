---
name: botzone-manual-live
description: Run and supervise one manually configured Botzone GuanDan live game with the local connector and auditable evidence. Use for single-game smoke or history/decision-trace sampling; do not use for batch capacity runs or workspace cleanup.
---

# Botzone Manual Live

Execute one user-configured Botzone game while keeping connector state and evidence attributable. The task prompt supplies the agent mode, seed, seat, fixed profile, budgets, expected starting inventory, and requested artifacts.

## Load context

Read the applicable `AGENTS.md`, `docs/CLEAN_HANDOFF.md`, and only the connector code/docs needed to confirm current CLI arguments and evidence schemas. Treat the task prompt's run-specific values as inputs, not long-term defaults.

## Establish the baseline

- Inspect `git status`; do not start live from an unexplained dirty tree.
- Verify the fixed workspace and expected empty/new-output inventory without printing secrets or private evidence.
- Confirm there is no attributable connector process and that every requested output path is new.
- Perform any command, path, token, or shell qualification in a temporary scratch location before live side effects.
- Run the requested zero-network preflight with the project interpreter. Configuration may load through the project's normal path, but never manually read or print `.env`, URLs, keys, cookies, headers, or tokens.

Preparation errors with no external table, request, durable state, or disclosed seed are correctable orchestration issues. Diagnose and retry them in place; do not convert them into a failed experiment.

## Start and connect

1. Start exactly one foreground connector through the supported launcher and retain a session handle that can be polled until exit.
2. Confirm the Botzone local-AI page says “已连接” before telling the owner the seed or asking for a table. Process liveness and long-poll timeout are not connection evidence.
3. Use browser control only for best-effort read-only inspection unless the task explicitly authorizes page writes. If the page cannot be read reliably, keep waiting and accept the owner's explicit connection/configuration confirmation.
4. After connection, send the owner the task-specific seed, seat, tribute setting, level, and agent. The seed becomes used at this message and must not be reused.
5. Ask the owner to create and configure one table and stop before Start. If reliable readback shows a mismatch, name the field and wait for correction. Otherwise accept the owner's explicit ready signal.
6. Restate the configuration and ask the owner to click Start once.

## Monitor the game

- Immediately watch the connector, first request, state, history, trace, and audit indicators. Once these prove play began, do not require another “started” reply.
- Keep the task open while waiting; provide brief low-sensitivity progress at least once per minute during active work.
- Do not expose hands, complete observations/actions, model text, identifiers, credentials, or private artifact contents in progress messages.
- Stop after the one requested qualified finish, an unrecoverable post-start failure, or the task's wall limit. Never create a second table to chase a strategy activation or cleaner result.
- Do not modify repository files or clean evidence during a live run. A discovered code defect ends the run with evidence preserved for a separate implementation task.

## Validate evidence

Use the current schemas rather than historical assumptions. At minimum verify:

- connector exit and absence of a residual process;
- audit parseability, requested agent mode, request/response/Header/finish counts, transport categories, and decision/model/source/fallback conservation;
- run provenance agreement with the single session or finished tombstone;
- requested history/trace status and their decision counts against the audit;
- no duplicate acknowledged decision and no unacknowledged pending decision in trace;
- expected files remain in place, with low-sensitivity size/hash inventory;
- Git HEAD/status did not change.

A nonfatal transport error that did not prevent completion or break delivery/ack conservation is a recorded transport observation, not an automatic reason to discard or replay the game. Preserve conservative history completeness markers when the connector did not observe the terminal tail.

Keep platform outcome validity separate from connector and decision-evidence validity. A qualified finish classified as `platform_error` is not a normal game result and cannot support win/loss claims, but acknowledged decision trace entries remain usable for per-decision diagnosis when their binding, sequence, selected-action, provenance, and audit conservation checks all pass.

## Report

Report the actual stage reached, ordering of connection/seed/config/start, process and aggregate counts, evidence status/inventory, Git status, and only genuine in-scope risks. Do not print private artifact bodies or sensitive identifiers. Return the untouched evidence to the planning Codex for strategy review.
