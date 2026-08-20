# 下一步实施提示词

## Step L5-A4e3：Botzone 容量运行本地 provenance token

L5-A4e2 唯一判定：

```text
botzone_paired_policy_failed_game_evidence_inconclusive
```

### 固定结论

- game 1 v7 audit 严格有效：exit 0、`finished_target`、request/response/Header=`27/27/27`、qualified finished=1、rule decisions=26、正常团队负、`score_0=1`，零 transport/协议/model/fallback 异常。
- 唯一 state 是严格最小 v3 finished tombstone，68 bytes，无 pending/effect/handler/cache。
- audit 为 701 bytes / SHA-256 `a277c492b7e7f826551bf60f9ce6b03cd86344fd7d95ddb6a68acefdb815b9f8`；state 为 68 bytes / SHA-256 `890d7427b8d5cbc477ab919c5847c11bb1d27fa913ead1d5250fb06d379db4c9`；只读审计前后均不变。
- 两者都不保存共同的 match 或本地运行标识。固定路径、策略模式和完成分类不足以证明属于同一次运行，关系只能是 `evidence_relation_unknown`。
- 旧 audit/tombstone 必须原样保留，不清理、不计分；25001/25002 seed 和容量根目录永久只读封存。

项目所有者常驻默认授权继续有效。本步骤是纯离线代码契约实现，不询问授权，不运行真实 connector、Botzone 或 DeepSeek。

### 目标

为每次受监督容量 connector 启动增加一个非敏感、调用方显式提供的本地 `run_token`。同一 token 必须进入该运行的 session/tombstone 和 completion audit，使两类本地证据可严格关联；token 不得进入 Botzone 请求/Header、DeepSeek prompt/request、Agent observation、合法动作或聚合 benchmark 报告。

### 推荐修改范围

- `integrations/botzone/session.py`
- `integrations/botzone/runner.py`
- `integrations/botzone/__main__.py`
- `evaluation/botzone_policy_benchmark.py`
- 对应 Botzone session/runner/CLI/policy benchmark 测试

如现有边界要求，可新增一个只含 token 校验常量/纯函数的 `integrations/botzone/run_provenance.py`。不得修改 engine、agents、DeepSeek client、transport、protocol、adapter、RAG、上传 Bot 或 docs。

### 契约要求

1. `run_token` 仅接受精确字符串，格式固定为 32 个小写十六进制字符；bool、非字符串、大小写、空白、长度错误和其他字符全部拒绝。token 由容量 manifest 离线生成，不从 match/player、牌、URL、key 或其他敏感值派生。
2. CLI 新增可选 `--run-token`。未提供时保持现有普通运行兼容；容量运行必须显式提供。preflight 不要求 token，也不得创建 session/audit。
3. `SessionStore` 在显式 token 模式下把同一 token 写入活动 session 和 finished tombstone；handler context、Agent 与 transport 不得接收该字段。
4. 保持旧 v3 session/tombstone 可严格读取；显式 token 使用新的 session/tombstone version，并要求 token 字段精确存在。不得把无 token 的旧文件静默升级或与 token 运行混用。
5. completion audit 在显式 token 模式下升级为新版本并包含同一 token；未提供 token 时现有 v7 字段、bytes 语义与测试保持兼容。audit 仍不得包含 match/session/player、牌、history、prompt、response、URL/key。
6. runner/CLI 必须把一个 token 同时传给 SessionStore 与 audit writer；缺失、不同或 malformed 时 fail-closed，不得生成可被误关联的 audit。
7. pending 重发、重启恢复与 finished cleanup 必须保留同一 token；使用不同 token 打开已有 token session 时返回固定诊断，不处理或覆盖原 state。
8. `PolicyAuditSubmission` 或等价内存输入可携带预期 token；新版本 audit 只有 token 精确匹配时才有效。token 不得进入 frozen aggregate report、`to_dict()`、diagnostics 或 repr。
9. benchmark 继续支持现有 v7 测试夹具和已封存 audit；新容量批次只接受带 token 的新版本 audit，不得把 v7 与 token 版本混在同一新批次。
10. 测试覆盖：严格 token 语法、CLI 传递、active→pending/inflight→finished 保持、重启同 token、不同 token 冲突、audit/session token 相等、默认兼容、benchmark 匹配/不匹配/缺失、报告脱敏、Agent/transport 隔离。
11. 全部测试使用 fake transport/client 和临时目录；网络、真实配置、`.env`、旧容量目录和现有 game 1 证据均不得读取。

### 验收

- 新增定向回归全部通过；
- 全量回归通过；
- `git diff --check` 通过；
- 默认无 token 的现有 v7 audit 与 v3 session/tombstone 快照保持兼容；
- 静态扫描确认 token 不进入 transport、Header、Agent、DeepSeek、RAG 或聚合报告；
- 建立独立实现检查点，提交范围仅限上述实现与测试文件。

成功时唯一判定：

```text
botzone_paired_policy_run_provenance_contract_verified
```

本步骤不生成新 manifest、state/audit 布局或 seed，不执行 preflight/live。通过后 L5-A4e4 才规划新 seed/root 与带 token 的容量恢复批次。
