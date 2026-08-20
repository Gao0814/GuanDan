# 下一步实施提示词

## Step L5-A4e2：game 1 audit/state 只读关系审计

L5-A4e1 未完成，唯一判定：

```text
botzone_paired_policy_failed_game_state_cleanup_invalid
```

### 新证据与停止原因

- game 1 completion audit 已存在，game audit 文件数为 1。
- 这与 L5-A4e1 的资格前提“game 1 audit 不存在”直接冲突，因此未读取 audit 正文、未解析 state、未删除文件、未写 cleanup audit。
- game 1 state 仍有 1 个活动文件；game 2–16 state 均为空。
- manifest 仍为 3256 bytes，SHA-256 `3af862cf31f9600746812b0534c4d0b66ce6c8fbd6fdc94c1331f19451b2607e`。
- cleanup audit 和临时 cleanup 文件均不存在；仓库未修改，零网络、零 connector、零 DeepSeek。
- 25001/25002 批次继续保持 `botzone_paired_policy_capacity_batch_invalid`；不得重开 game 1 或启动 game 2–16。

项目所有者常驻默认授权继续有效。本步骤是纯只读审计，不询问项目授权，不删除或写入任何容量文件。

### 目标

在不输出原始 audit/state 内容的前提下，确认新出现的 game 1 v7 audit 与残留 state 是否能被归为同一次未完成运行，并确定后续是否具备精确清理资格。不得预设 audit 表示成功完成。

### 执行要求

1. 只读复核 HEAD、工作区、无残留 Python connector，以及 manifest bytes/hash。进程检查仅枚举 `python.exe/pythonw.exe` 且要求独立 `-m integrations.botzone` 参数。
2. 严格复核布局：game 1 audit 目标精确存在 1 个普通文件；game 1 state 精确存在 1 个普通文件；game 2–16 state 为空；其他 15 个 game audit 目标不存在；不得存在额外文件、目录或链接。
3. 记录 game 1 audit/state 的 bytes 与 SHA-256，用于前后只读不变性验证；不得输出文件名以外的 session/match 标识。
4. 严格解析 game 1 audit 的 v7 schema、version、固定字段集合、整数/bool 类型、守恒和 allowlist。只输出固定聚合：exit code、stop reason、agent mode、cycles、request/response/header、transport timeout/failure、finished raw/qualified/classification、diagnostics 是否为空、决策来源、模型尝试/结果、fallback 与结果聚合。
5. audit malformed、未知 schema/字段、守恒失败、敏感字段命中或 agent mode 与 manifest game 1 不符时，立即判 inconclusive；不得继续解析 state。
6. 严格解析唯一 state 的当前 session schema/version、文件名—内部 key 一致性、stage、delivery、finished、pending response/effect、handler/cached response 的存在性。不得输出 key、digest、牌、history、response 或玩家内容。
7. 只按以下固定关系分类：
   - audit 为 exit 0 / `finished_target` / qualified finished，而 state 不是最小 finished tombstone：`completed_audit_state_conflict`；
   - audit 为未完成或失败停止，state 为同一 game 1 的非 finished 活动 session：`abandoned_session_consistent`；
   - audit 与 state 都表示相同 qualified finished：`finished_evidence_consistent`；
   - 其他任何组合：`evidence_relation_unknown`。
8. 不使用时间戳、文件创建顺序或猜测补足关联；不能从固定路径、agent mode、完成分类和结构守恒证明关系时必须保持 unknown。
9. 结束时重新验证两个源文件的 bytes/SHA-256 和整个布局不变。不得创建 summary、临时文件或 cleanup audit；只在最终回复中报告脱敏固定聚合。
10. 本步骤不得删除 state/audit、运行测试/preflight/connector、访问 Botzone/DeepSeek、修改仓库或开始新批次。

### 判定

仅当 audit/state 均严格合法且关系分类不是 unknown 时：

```text
botzone_paired_policy_failed_game_evidence_reconciled
```

否则：

```text
botzone_paired_policy_failed_game_evidence_inconclusive
```

若分类为 `abandoned_session_consistent`，下一步 L5-A4e3 才依据常驻授权精确删除该 state，并保留 game 1 audit。若为 completed/conflict/unknown，不得清理，必须按分类另行规划。新 seed/root 与 connector 存活握手均排在证据处置之后。
