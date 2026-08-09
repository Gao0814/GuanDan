# 下一步实施提示词

## Step L2-A1b：Botzone 官方首个 play 请求契约补全

请在 GuanDan 项目中完成 Step L2-A1b。本步仍属于 Phase 3 准入加固：不得接 Agent、不得实现 play adapter、不得实现真实 HTTP transport、不得联网，只补全官方无贡裁判实际输出与 durable session 之间的协议契约。

### 前置与检查点

L2-A1a 历史判定保持：

```text
botzone_phase3_admission_contract_verified
```

它已验证 claim 虚拟 ID multiplicity、`HandlerContext`、`HandlerResult` / `PlayEffect`、ack 后扣牌和累计 history，定向 34 项、全量 480 项通过。但随后用已封板的官方裁判源码构造精确首个无贡 `play` 请求时，发现三项未覆盖输入，因此 Phase 3 准入重新打开。

开始本步前，必须先复核并创建一个只包含当前 L2-A1a 六个修改文件的独立检查点，不得把 docs 或本步修复混入：

- `integrations/botzone/connector.py`
- `integrations/botzone/protocol.py`
- `integrations/botzone/session.py`
- `tests/test_botzone_connector.py`
- `tests/test_botzone_protocol.py`
- `tests/test_botzone_session.py`

### 已复现的官方输入差异

#### 1. play global 包含 resist=false

官方无贡分支在四次 deal 后设置：

```text
global.resist = false
```

随后生成首个 `play`。当前 `_global_state()` 只接受 `level/tribute/first/last` 四个键，会返回：

```text
ProtocolValidationError: global has unsupported or missing fields
```

必须实现 stage-specific 严格校验：

- `deal` 继续接受官方 deal 的基础 global；
- 无贡 `play` 必须接受并规范化严格布尔 `resist=false`；
- `resist=true`、truthy 值、非 bool、贡还字段或未知扩展仍 fail-closed；
- 不因兼容官方字段而放宽 `tribute=0`、`first/last=null` 的无贡边界。

#### 2. history 是固定四槽窗口

官方首个无贡 `play.history` 为：

```json
[[], [], [], []]
```

之后裁判使用 `history[1:] + current_move` 滑动，因此早期窗口会同时包含空槽和真实 `{player,response}`。当前 parser 要求每项都是对象，会返回：

```text
ProtocolValidationError: history[0] must be an object
```

必须：

- 严格接受官方空槽 `[]`，并规范化为“不存在的历史事件”；
- 真实槽仍只接受精确 `{player,response}`；
- 固定窗口最多四槽，空槽只能形成前缀，真实事件后再次出现空槽必须拒绝；
- `{}`、`null`、非空数组、额外字段和超过四槽仍拒绝；
- 规范化后的 `PlayRequest.history`、session `latest_window/history` 只含真实公开事件；
- 首个窗口、逐步填充、完整四手、滑动窗口、pass 和输入不变性均有测试。

#### 3. play 回合缺少本地座位

Botzone `PlayRequest` 不含 `your_id`；当前 `SessionRecord` 未保存 deal 的 `your_id`，`HandlerContext` 也没有本地座位。Phase 3 因而无法构造正确的 engine `player_id`、队伍和 Agent 实例。

必须：

- 在 deal 时持久化严格 `0..3` 的 `local_player_id`；
- 后续 play、失败恢复、pending 重放和重启后保持不变；
- `HandlerContext` 暴露该座位，但普通日志、异常、聚合报告不得输出 match key 或完整手牌；
- Botzone `0..3` 到 engine `1..4` 的转换只提供纯函数并测试，不在本步调用 Agent；
- 同 match 重复或冲突 deal、旧 schema、malformed seat 均 fail-closed；
- schema version 必须升级，不得把旧 snapshot 静默解释为新结构。

### 官方桌面语义锁定

为下一步 adapter 增加纯协议 fixture，锁定官方裁判已确认的当前回合语义，不生成 engine action：

- `done` 按出完顺序追加玩家；元素严格唯一且为 `0..3`；
- `pass_on` 为 `-1` 或刚出完、尚待接风处理的玩家 ID；
- 当前玩家是否自由领牌，按官方裁判从 latest window 末尾向前扫描：遇到当前玩家上一手即停止；此前若无非 pass 动作则为 free，否则最后一个非 pass 是桌面领牌；
- 无法从本地座位、latest window、`done/pass_on` 得到唯一一致状态时 fail-closed，不猜测领牌者或伪造 pass。

该部分可以新增 frozen/slots 的纯协议 view/helper，但不得导入 Agent、调用 `BaseRuleEngine` 或构造业务 observation。

### 允许修改

- `integrations/botzone/models.py`
- `integrations/botzone/protocol.py`
- `integrations/botzone/session.py`
- 必要时 `integrations/botzone/connector.py`
- 对应的 `tests/test_botzone_protocol.py`
- `tests/test_botzone_session.py`
- `tests/test_botzone_connector.py`
- `tests/test_botzone_profile.py`

不得修改 `engine/`、`agents/`、现有 CLI、RAG、evaluation 或 DeepSeek。

### 必测场景

- 官方首个无贡 play 原样 fixture：`resist=false`、四个空 history 槽、`done=[]`、`pass_on=-1`；
- history 从 0/1/2/3/4 个真实事件逐步填充并滑动；非法空槽位置整体拒绝；
- deal/play global 的 stage-specific 字段集合；严格 bool 和未知字段反例；
- 四个本地座位分别持久化、重启恢复、多 match 隔离和冲突 deal；
- schema 升级、旧 snapshot、损坏 seat 和 context 完整 `to_json()`；
- free lead、敌方/队友领牌、全 pass 回到当前玩家、玩家完成后的跳过和 `pass_on` 一致性；
- 保持 9/10 张炸弹、pending effect、history merge、mock connector 全部回归通过；
- 边界扫描继续禁止网络、真实 URL、`.env`、环境变量、Agent/engine/CLI 导入和敏感值。

验证命令：

```text
python -m unittest tests.test_botzone_protocol tests.test_botzone_session tests.test_botzone_connector tests.test_botzone_poll tests.test_botzone_cards tests.test_botzone_profile -q
python -m unittest discover -q
git diff --check
```

### 验收判定

全部官方 fixture、持久化和回归通过时，唯一判定：

```text
botzone_phase3_official_request_contract_verified
```

该判定才允许下一步 Step L3-A1 实现离线 RuleBasedAI play adapter。它不代表 Agent 已接入、存在 live 启动命令、可以联网或支持贡还/升级。

### 最终报告

报告 L2-A1a 检查点、官方首个 play fixture、global/history/local seat 三项修复、桌面语义 helper、定向/全量回归和边界扫描。明确说明未调用 Agent、未修改 engine、无真实 transport、未读取 URL/密钥、未联网。
