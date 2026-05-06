# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

A single-game GuanDan (掼蛋) card game engine with an AI decision layer. The architecture follows a strict two-layer separation:

- **Engine** (`engine/`): The source of truth for all rules — pattern recognition, legal action generation, action comparison, state advancement, and game-over detection.
- **AI** (`agents/`): Reads `observe()` + `legal_actions()` public payloads, returns an `action_id`. Never touches engine internals or makes legality decisions.

Core principle: **the engine decides "can you play this", the AI decides "which to play"**.

## Build / test / run commands

```bash
# Run all tests
python -m unittest discover -q

# Run specific test modules
python -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_cli_debug_output -q

# Rule-based AI self-play (default)
python -m cli.run_4ai_debug --seed 7

# DeepSeek AI self-play (requires DEEPSEEK_API_KEY in .env)
python -m cli.run_4ai_debug --agent deepseek --seed 7
```

## Architecture

### Two-layer design with a strict boundary

```
CLI / caller
    │
    ├─ observe()         → dict (5 info blocks, no internal state objects)
    ├─ legal_actions()   → list[dict] (pre-expanded canonical actions)
    ├─ step(action_id)   → advances state, returns result dict
    │
    ▼
Engine (engine/game.py → GuanDanGame)
    │
    ├─ engine/rules.py    → BaseRuleEngine: legal action expansion, pattern detection, comparison
    ├─ engine/patterns.py → Pattern detection for all 10 supported pattern types
    ├─ engine/state.py    → Immutable dataclasses: GameState, PlayerState, TableConstraint
    ├─ engine/actions.py  → Action dataclass (declared_pattern, declared_cards, carrier_cards, wildcard_info)
    └─ engine/cards.py    → Card, card_to_token, sort keys, rank/suit constants

AI Layer (agents/)
    │
    ├─ agents/base.py          → BaseAgent ABC with select_action(observation, legal_actions) → action_id
    ├─ agents/rule_based_ai.py → RuleBasedAIAgent: sorts by wildcard count, then hand size
    ├─ agents/deepseek_ai.py   → DeepSeekAIAgent: calls DeepSeek API, falls back to rule-based on failure
    ├─ agents/deepseek_client.py → DeepSeekClient: HTTP client, returns DeepSeekSuggestion(action_id, reasoning)
    └─ agents/rag_advisor.py   → RAGAdvisor: retrieves rule/experience evidence for DeepSeek prompts
```

### Observation structure (returned by `observe()`)

Five fixed info blocks, always as dicts (never raw engine objects):
1. `my_info` — player_id, team, hand_cards, hand_count, remaining_single_card_count
2. `current_round` — step_no, round_no, current_player_id, current_level_rank, table_action, constraint
3. `other_players` — list of {player_id, team, hand_count, finished, finish_rank}
4. `history` — actions tail (last 12) and finish_order
5. `legal_actions` — full action list (same as `legal_actions()` return)

### Action dict structure (from `legal_actions()`)

Every action is pre-expanded with explicit wildcard declarations:
- `action_id`: int
- `declared_pattern`: str (one of the 10 supported types or "pass")
- `declared_cards`: list[str] — the logical cards (for comparison)
- `carrier_cards`: list[str] — the physical cards (for deduction from hand)
- `wildcard_count`: int (0 or 1)
- `wildcard_info`: list[dict] — what each wildcard is declared as

### Key invariants (from docs/INVARIANTS.md)

- 108 cards total, 27 per player, 2 decks
- Teams: 1&3 vs 2&4
- Wildcard (逢人配) = red-heart level-rank card, max 1 per action
- Jokers: only single, pair, or 4-joker-bomb (天王炸) — no other joker combinations
- Straights: fixed 5 cards, only A2345 / 23456 / 10JQKA allowed, JQKA2 forbidden
- Straight flush sits between 6+ bombs and 5-bombs in the cross-type hierarchy
- Game ends when 3rd player finishes; if head-player's teammate is last → draw, otherwise head-player's team wins

### What belongs where

| Concern | Location |
|---|---|
| Pattern detection | `engine/patterns.py` |
| Legal action expansion, comparison, wildcard substitution | `engine/rules.py` |
| Game loop, state advancement, observation building | `engine/game.py` |
| Immutable state types | `engine/state.py`, `engine/actions.py` |
| Card model, token conversion, sort order | `engine/cards.py` |
| Agent interface | `agents/base.py` |
| AI decision logic | `agents/rule_based_ai.py`, `agents/deepseek_ai.py` |
| DeepSeek HTTP client | `agents/deepseek_client.py` |
| CLI debug replay | `cli/run_4ai_debug.py` |
| RAG knowledge retrieval | `rag/retriever.py`, `rag/kb_loader.py` |

### Modification rules

- **Never modify `engine/`** when only changing AI behavior — AI should only consume public payloads.
- **Never modify `tests/` or `docs/`** unless explicitly asked.
- Changes to `engine/` require running the full test suite (`test_patterns`, `test_rules`, `test_game_flow`, `test_cli_debug_output`).
- Legacy code (multi-game, old evaluation pipeline, old DeepSeek experiments) lives in `archive_legacy/` and is out of scope.

### DeepSeek agent details

- `DeepSeekAIAgent.verbose` controls debug output. Set to `True` only for player 1.
- The agent handles all printing itself; it passes `verbose=False` to `DeepSeekClient.suggest_action_id()`.
- `DeepSeekSuggestion` carries both `action_id` and `reasoning` (the model's chain-of-thought).
- On any failure (API error, invalid action_id), the agent falls back to `RuleBasedAIAgent`.
- RAG context is optional — if `rag_advisor` is `None`, the prompt omits RAG evidence.
