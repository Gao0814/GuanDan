# GuanDan Phase-1

This repository currently implements Phase-1 core capabilities:

- Rule subset for single, pair, triple, bomb(4 same rank), and pass
- Legal action generation for lead/follow contexts
- Action validation and state transition with round-end and game-over handling
- 4-AI automatic game loop with full debug events
- Baseline rule+experience heuristic AI (no learning/training)
- Local RAG knowledge loading and retrieval with strict source boundary

## Run 4-AI Debug

Use Python 3.11 environment in this workspace:

```bash
d:/VsCodeProject/GuanDan/.venv/Scripts/python.exe -m cli.run_4ai_debug --seed 7 --max-steps 12000
```

Example output:

```text
game_over=True winner=2 steps=... rounds=... events=...
```

## Run Tests

Run full Phase-1 test suite:

```bash
d:/VsCodeProject/GuanDan/.venv/Scripts/python.exe -m unittest tests.test_patterns tests.test_rules tests.test_game_flow tests.test_rule_based_ai tests.test_rag_constraints -v
```

## Phase-1 Supported Scope

- Supported patterns: single, pair, triple, bomb (exactly 4 same rank)
- Supported action type: pass (action only, not a pattern)
- Follow rules:
	- table single/pair/triple: bigger same-type, or bomb, or pass
	- table bomb: bigger bomb, or pass
- Rule engine is the only truth source for legality and state update
- RAG is knowledge support only and cannot replace rule truth

## Out Of Scope In Phase-1

- Any online LLM/API call or training pipeline
- RL, self-play, MCTS, autonomous learning
- Phase-2 and Phase-3 features
