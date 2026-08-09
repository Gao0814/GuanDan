# 下一步实施提示词

## Step L1-A1：Botzone 无贡协议模型与 108 ID codec

请在 GuanDan 项目中完成 Step L1-A1。本步只实现离线、纯数据的 Botzone GuanDan 协议模型、108 ID 映射和单元测试；不得实现或启动 connector，不得联网，不得创建/加入对局，不得读取本地 AI URL、连接密钥、`.env`、Cookie、Header 值或账号信息，不得调用 Agent、DeepSeek 或现有 CLI，不得修改 `engine/`、`agents/`、`cli/`、`rag/` 或 `evaluation/`。

### 前置结论

Phase 0 已由官方 Wiki、GuanDan 游戏详情的官方裁判源码和目标账号脱敏配置页证据封板，唯一判定：

```text
botzone_manual_no_tribute_phase0_verified
```

官方裁判源码副本为 31,136 bytes，SHA-256：

```text
20d06056689341e1745837564dfae325bd56e54c7b0337bc11c6e8c856bc6b46
```

来源为 `https://www.botzone.org.cn/game/GuanDan` 的“裁判代码”，核对日 2026-08-09。协议说明为官方 GuanDan Wiki `oldid=2497`，local-AI transport 说明为“本地 AI”`oldid=2230`。

### 允许修改

建议只新增：

- `integrations/__init__.py`
- `integrations/botzone/__init__.py`
- `integrations/botzone/models.py`
- `integrations/botzone/cards.py`
- `integrations/botzone/protocol.py`
- `tests/test_botzone_cards.py`
- `tests/test_botzone_protocol.py`
- `tests/test_botzone_profile.py`

如现有目录约定要求更少文件，可合并模块，但不得扩展到 Phase 2 connector/session 或 Phase 3 Agent adapter。

### 必须实现的协议契约

1. 108 个实体 ID：每副 `0..53`，普通牌按 A、2..K 和 `h,d,s,c`，`52/53` 为小/大王；第二副为 `+54`。双向映射必须保留实体副本 ID。
2. 玩家编号保持 Botzone `0..3`；本步不转换为 engine `1..4`。
3. `deal` request：严格解析 `stage`、27 张 `deliver`、`your_id`、`global`；response 精确为 `[]`。
4. `play` request：严格解析近四手 `history`、`done`、`pass_on`、`global.level`；response 模型精确为 `[action, claim]`，pass 为 `[[], []]`。
5. 无贡 profile：`global.tribute == 0`、`first/last == null`；四家 deal 后首个 play 为 Botzone 玩家 0。`tribute`、`return` 和未知 stage 必须返回结构化 `unsupported_stage`，不得伪造 response。
6. claim 校验按官方裁判语义建模：action/claim 等长；非红桃级牌的 action 牌面必须在 claim 多重集中对应；剩余 claim 牌面数量等于配子数量且不得声明为王；claim 顺序不影响语义；两副相同牌在 claim 中按牌面等价。
7. 所有对外编码只输出 `0..107`。即使官方裁判源码对 claim 的范围/重复校验较宽松，本项目也不得依赖该宽松行为。
8. Botzone 物理牌池最多有两张红桃级牌，因此协议模型允许识别最多两个配子；当前 engine 每手最多一个配子的能力差异只记录，不在本步修改 engine。

### Fail-closed 要求

- `bool` 不得冒充整数；
- 非法 ID、错误类型、错误数组长度、重复实体 action ID、action 不属于已知本家实体手牌、错误 stage 和 malformed history 必须整体失败；
- 不保留部分解析结果，不生成默认动作，不把未知字段猜成已确认语义；
- 数据模型优先使用 `@dataclass(frozen=True, slots=True)`，mapping/sequence 输出不可变且 JSON 友好；
- 不在异常、repr、fixture 或测试快照中出现真实 URL、密钥、match ID 或账号数据。

### 测试要求

- 108 ID 全覆盖 round-trip，以及 A/2/K/双王、四花色、第二副边界；
- deal/play/pass 正常编解码；
- 自然牌 `action == claim`；
- 单配子和双配子的 carrier/claim 差异、非王声明、顺序无关和副本等价；
- claim 等长、多重集守恒和非法王声明失败；
- 无贡 `deal × 4 → player 0 play` fixture；
- `tribute/return/unknown` 统一 unsupported，确认不会产生 Agent response；
- malformed、非法 ID、bool、重复 action ID 和输入不变性；
- 扫描确认没有网络库、环境变量、`.env`、API key、Botzone URL、engine 私有状态或 runtime 反向导入。

先运行新增定向测试，再运行：

```text
python -m unittest discover -q
git diff --check
```

### 验收判定

全部契约和回归通过时，唯一判定：

```text
botzone_no_tribute_protocol_verified
```

该判定只允许进入 Phase 2 mock connector/session，不代表 connector 已可启动、RuleBasedAI 已接入、真实 Botzone 可用或完整支持贡还/升级规则。

### 最终报告

报告修改文件、数据模型、108 ID 公式、claim 语义、无贡阶段 fixture、unsupported stage 行为、定向/全量测试与边界扫描。明确说明未联网、未读取连接 URL/密钥、未调用 Agent、未修改 engine、未实现 connector。
