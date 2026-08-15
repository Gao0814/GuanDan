# 下一步实施提示词

## Step L5-A4a：Botzone finished score 结果观测契约

L5-A3d 已完成，唯一判定：

```text
botzone_observed_live_tombstone_cleanup_verified
```

L5-A3c 的唯一 finished tombstone 已严格验证并删除，state 文件数 `1 → 0`，目录保留且为空；v6、v5 与既有 cleanup audits 均未改变。新 cleanup audit 为 345 bytes，SHA-256：

```text
a71e233af98d55000a074413b8f4cc97e564db484bf52b5c204e5758681a0225
```

当前 v6 已证明模型动作实际进入 Botzone 响应，但 runner/audit 尚未保留平台 finished row 的安全结果聚合，无法比较 RuleBased 与 DeepSeek。本步骤只离线实现结果观测契约，不运行 preflight、connector、runmatch 或任何网络请求。

### 官方结果语义

以项目所有者提供、来源为 Botzone GuanDan 游戏详情页的官方裁判源码为准：

- 正常 `settle()`：胜方同队两名玩家得到相同的 `1`、`2` 或 `3`，负方同队两名玩家均为 `0`；
- `3`：头两名属于同队；
- `2`：第一名与第三名属于同队；
- `1`：第一名与第四名属于同队；
- `setError()`：违规玩家 `-2`、其队友 `0`、两名对手各 `1`；该结果不得计入正常动作质量样本；
- 队伍仅由座位奇偶确定：`0/2` 与 `1/3`。

不得根据单次 live 的分数猜测语义，也不得修改 `FinishedRow` 的原始严格解析。

### 范围

优先新增：

- `integrations/botzone/result_observability.py`
- `tests/test_botzone_result_observability.py`

仅在确有需要时最小修改：

- `integrations/botzone/connector.py`
- `integrations/botzone/runner.py`
- 与 finished/audit 契约直接相关的现有 Botzone 测试

禁止修改：

- `engine/`、`agents/`、RAG、配置与 `.env`
- Botzone cards/models/protocol/poll/session/transport 解析和事务语义
- DeepSeek 动作选择、fallback 与 L5-A3a 观测分类
- 上传 Bot ZIP
- `docs/`

### 固定结果模型

新增 frozen/slots、JSON 友好的不可变快照与受控 recorder。只允许聚合整数，不保留逐局 row、座位、scores tuple、match 或玩家标识。

每个 `finished_qualified` 必须精确归入一个固定结果类别：

- `local_team_win`
- `local_team_loss`
- `platform_error`
- `invalid_score_shape`

正常结果必须同时满足：

- `local_player_id` 为严格非 bool 整数 `0..3`；
- scores 精确四项，元素均为严格非 bool 整数；
- 同队两项相等；
- 一队精确为 `0/0`，另一队精确为 `1/1`、`2/2` 或 `3/3`；
- 本家所在队为正分时是 `local_team_win`，并记录固定 score bucket `score_1/score_2/score_3`；本家队为 0 时是 `local_team_loss`，记录 `score_0`。

只有精确 `-2/0/1/1` 且 `-2` 玩家队友为 0、两名对手为 1 时才归类 `platform_error`。其他长度、类型、范围、同队不一致、两队同时为正、全零或异常组合统一归类 `invalid_score_shape`，不得抛出原始内容或伪造正常结果。

### 记录时点与守恒

- 只在现有 connector 已判定同实例、已 ack play、四人、state cleanup 成功并将 row 计为 `qualified` 时记录一次结果。
- aborted、non-four-player、four-player-unqualified、重复 finished、历史 tombstone、不同 match、deal-only、未发送/未 ack play 均不记录结果。
- result recorder 失败不得改变 finish cleanup、qualified 判定或 Agent cache release；但必须使结果快照失效，v7 audit 拒绝写入部分结果指标。
- `finished_qualified == sum(result_category_counts)`。
- `normal_result_count == local_team_win + local_team_loss`。
- `normal_result_count == sum(local_team_score_counts)`。
- `platform_error` 与 `invalid_score_shape` 不进入 score buckets。
- finished cleanup 不清空 runner 生命周期累计结果；重复 poll 不重复计数。

### Runner 与 v7 audit

`RunnerSummary` 以安全默认值新增：

- `result_category_counts`
- `normal_result_count`
- `local_team_score_counts`
- `result_observability_valid`

audit 从 v6 加法升级为 v7，保留 v6 全部字段、名称和语义，仅新增固定结果聚合。数组按类别名稳定排序；`write_audit()` 写盘前严格复核 allowlist、类型、canonical 顺序与全部守恒。`result_observability_valid` 只作为内部写盘门槛，不需要持久化；失效时不写任何 audit。

现有 `exit_code_for()`、qualified finished、协议诊断、Agent/模型守恒和 CLI stdout 保持不变。正常 live 若出现 `platform_error` 或 `invalid_score_shape`，协议闭环可保留，但后续动作质量评估必须排除该局并报告固定计数。

### 必须新增的离线测试

1. 快照 frozen/slots、稳定 JSON、严格整数、allowlist、canonical 顺序和全部守恒。
2. local seat `0..3` 下，双方分别以 score `1/2/3` 获胜的全部正常分类。
3. 四种违规玩家位置的精确 `-2/0/1/1` platform-error 分类。
4. bool、错误长度、同队分数不一致、负数异常、超范围、双方同时正分、全零和其他畸形组合统一 invalid。
5. 只有 qualified finished 记录；unknown/aborted/non-four/unqualified/duplicate/deal-only/未 ack 不记录。
6. cleanup、cache release、pending resend、transport failure/timeout 和重复 finished 不重复计数。
7. recorder/snapshot 异常不改变 connector 行为，但 v7 audit fail-closed。
8. v7 audit 精确字段快照；v6 所有字段逐项不变；手工 malformed summary 拒绝写入。
9. audit/repr/异常不含 scores tuple、seat、player、match、牌、history、action、prompt、response、URL、key 或异常正文。
10. 全部使用 synthetic finished rows 与 fake transport，真实网络计数为 0。

最低验证：

```text
python -m unittest tests.test_botzone_result_observability tests.test_botzone_finished_provenance tests.test_botzone_agent_observability tests.test_botzone_live_preflight -q
python -m unittest discover -q
git diff --check
```

### 验收判定

全部门槛通过时唯一判定：

```text
botzone_finished_score_observability_verified
```

完成后建立只含本步骤允许文件的独立 Git 检查点。不得读取真实配置或 state/audit 内容，不得联网、运行 preflight/connector、创建对局或请求 live 授权。

该判定只证明平台 score 可被安全聚合，不代表已有足够样本或 DeepSeek 优于 RuleBased。后续 L5-A4b 再离线设计固定 seed、同座位、同对手版本的成对 RuleBased/DeepSeek 赛程与微聚合报告。
