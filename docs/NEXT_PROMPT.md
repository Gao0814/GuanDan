# 下一步实施提示词

## Step K-A3d3c3a：K-A3d3c2 源证据独立只读恢复审计

请在 GuanDan 项目中完成 K-A3d3c3a。本步只读取 K-A3d3c2 已落盘的 runner、ledger、aggregate report 和状态文件，在全新的仓库外目录运行两次独立恢复 verifier。不得修改原证据、不得联网、不得调用模型、不得读取 `.env` 或 API key，也不得创建新的 live runner。

### 必须保留的原结论

K-A3d3c2 唯一正式结论永久保持：

```text
strategy_intent_live_quality_recovery_invalid
```

原因是原运行缺少 `manifest.json` 和 `completion.json`。独立恢复审计即使成功，也不能追认或改写 K-A3d3c2，只能产生新的 K-A3d3c3a 只读恢复结论。

K-A3d3b 仍为 `strategy_intent_live_quality_benchmark_invalid`，seed `600..609` 继续禁用；K-A3d3c2 的 seed `700..709` 也不得再次用于 live 运行。

### 原证据位置

候选根目录：

```text
C:\Users\86166\AppData\Local\Temp\guandan-strategy-intent-quality-k-a3d3c2-4cb68ee-a41e72a630154366b4ae0ecda18fe594
```

原 audit 目录：

```text
C:\Users\86166\AppData\Local\Temp\guandan-strategy-intent-quality-k-a3d3c2-4cb68ee-a41e72a630154366b4ae0ecda18fe594\audit
```

已知文件：

```text
candidate root/
  launch_live_quality.py       3013 bytes
  live_quality_runner.py      15901 bytes
  audit/
    audit_summary.json          728 bytes
    call_ledger.jsonl         10982 bytes
    failure.json                189 bytes
    heartbeat.json              144 bytes
    launch_state.json           606 bytes
    process_state.json          351 bytes
    report.json               28488 bytes
```

锁定 hash：

```text
report.json        d931a5cf...5457b05
call_ledger.jsonl  1d786476...3484a6aa
audit_summary.json 26a583fb...bb7be1a4
failure.json       f32add93...152fd00a
process_state.json 2ace9141...5a51afff
```

执行时必须计算并报告全部完整 SHA-256，不得只保留缩写。还要计算父启动器、子 runner、heartbeat 和 launch state 的 bytes/hash。

### 已确认的故障机制

只读复核 `live_quality_runner.py`：

- report 读取和独立 `validate()`：第 237–238 行；
- verdict 计算：第 239 行；
- `audit_summary.json` 写入：第 240–241 行；
- process state 转为 `completed`、heartbeat completed：第 242–243 行；
- manifest 文件列表和写入：第 244–245 行；
- completion 写入：第 246 行。

第 244–245 行把 `live_quality_runner.py` 作为 `audit_dir/live_quality_runner.py` 读取 metadata，但实际 runner 位于 candidate root。该路径不存在，导致 manifest 写入前抛出异常，随后外层失败处理把子状态从 `completed` 转为 `failed`。这只能证明完成审计链的路径错误；不能在 verifier 通过前假设 report、ledger 或质量指标有效。

### 仓库与安全前置

1. 记录 HEAD 和 `git status --short`；工作区必须干净。
2. 只读复核原目录文件集合、bytes 和完整 SHA-256；不得修改时间戳或内容。
3. 确认原目录仍缺少 manifest/completion，且没有新增文件。
4. 不导入或执行原 live runner，不调用其 `main()` 或 provider。
5. 不读取 `.env`、进程 key 内容、prompt、action ID、response body 或 reasoning。
6. verifier 只能使用 Python 标准库和纯离线聚合逻辑；不得导入 `DeepSeekClient`。
7. 原授权已用尽，本步不得发出任何网络请求。

### 独立 verifier

在新的仓库外恢复目录创建 verifier。它必须从零实现并交叉验证，不得直接信任原 `audit_summary.json` 的 `integrity_pass` 或 verdict：

- JSON/JSONL 可解析、无 NaN/Infinity；
- ledger sequence 连续 1..48，off/on 各 24；
- 每条请求均有 started 后的唯一 terminal 记录；terminal 均为 returned，failed=0；
- timeout=60、retries=0、endpoint/model 与锁定值一致；
- report 的三策略、四阶段、selected、AB/BA、provider validity、pair、branch、W/D/L、质量比较和 phase-to-overall 守恒；
- 三策略均 10/10/0，每 policy×phase selected=2，整体 24 pair；
- 所有必要 rollout branch complete，diagnostics/invalid/timeout/step-limit 为 0；
- report、ledger 与原 audit summary 的非 verdict 聚合字段逐项一致；
- 原状态链确实为 `bootstrapping → imports_ready → startup_ready → running → completed → failed`；
- 父状态为 `spawning → spawned → exited`，child exit code=1；
- failure class/stage 与 `unexpected_failure / report_validation` 一致；
- 源码与文件布局精确支持第 244–245 行路径错误，且该错误发生在 report/summary 后、manifest/completion 前。

verifier 不得通过生成或补写原目录的 manifest/completion 来“修复”证据。所有恢复输出只能写入新的恢复目录。

### 双运行与恢复输出

verifier 必须运行两次，分别写入 `run1.json`、`run2.json`：

- 两份输出逐字节和 canonical JSON 完全一致；
- 不包含时间、PID、绝对 key、prompt、action、response、手牌、玩家或样本身份；
- 输出完整源文件 manifest、全部完整性检查和重新计算的 aggregate metrics；
- 生成独立 `recovery_summary.json` 与 `manifest.json`，记录所有恢复文件 bytes/SHA-256；
- 原证据目录在前后 hash/文件集合完全一致。

### 判定顺序

先做恢复完整性。任一输入、守恒、文件、状态链、双运行或隐私检查失败，唯一判定：

```text
strategy_intent_live_quality_readonly_recovery_invalid
```

不得解释质量指标。

只有恢复完整性全部通过，才按 K-A3d3c2 预注册顺序解释：

1. changed pair < 8：`no_observed_strategy_intent_action_quality_gain`；
2. `on_better_count <= off_better_count`：同上；
3. on team win count < off team win count：同上；
4. 否则：`retain_for_expanded_strategy_intent_quality_evaluation`。

恢复结论仍是小样本、RuleBased 续局代理下的描述性结果，不是显著性、因果或胜率结论，也不授权默认启用 strategy intent prompt。

### 最终报告

必须包含：

- K-A3d3c3a 唯一判定；
- K-A3d3c2 invalid 永久保留声明；
- HEAD、工作区、原目录前后文件集合与完整 SHA-256；
- 第 237–246 行执行顺序和已确认路径缺陷；
- 48/48 ledger、off/on、report/策略/阶段/branch 守恒；
- verifier 双运行 hash 和恢复目录全部文件 manifest；
- 若完整性通过，报告 changed、on/off better、team wins 和按预注册顺序得到的描述性判定；
- 明确说明未修改源证据、未联网、未调用模型、未读取 `.env` 或 key。
