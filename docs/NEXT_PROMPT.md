# 下一项 Coding 任务：修正 M3 牌型校验并完成记牌效果对照

你是 Coding Codex。先读 `AGENTS.md`、适用项目 Skills、`README.md`、`CLAUDE.md`、`docs/PROJECT_STATUS.md` 与 `docs/PLAN.md` 顶部、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`，再核对 Git status/diff/HEAD、`e10057d` 差异及相关测试。当前项目范围是固定级牌 2、四人、无贡单局。你负责业务代码和 tests；不修改规划文档，不碰两个 Botzone workspace、`.env`、真实 connector 或页面。所有者才操作 Botzone。

## 目标与已知事实

`e10057d` 已把公开牌池、各家余牌容量和合法候选对照加入默认 DeepSeek 请求，禁网 Request/ID/source 闭环成立，但真实模型动作质量未评测。规划发现一项可复现的 M3 校验错误：引擎合法天王炸是 2 小王加 2 大王共 4 张，`agents/card_tracker.py` 的 `_valid_play_card_count("joker_bomb", n)` 却要求 2 张。以引擎真实出过天王炸后的下一位公开观察生成摘要，结果错误降为 E0。连对在引擎固定为 3 对共 6 张，当前校验却接受任意 6 张以上偶数张。修正两处并完成少量同状态选择对照，作为**一个**任务；不要拆成只有资格检查的阶段。

## 实施与验收

1. 让记牌器历史和候选的牌型长度校验与引擎一致：`joker_bomb` 恰好 4、`pair_straight` 恰好 6。通过真正的 `GuanDanGame` 合法出牌生成完整历史做回归：四王天王炸之后的下一位仍能保留 E1/E2 中可证明的牌池事实；伪造的 2 张王炸或 8 张连对不得误作有效历史。保持异常历史保守 E0、实体牌守恒、公开容量及 action ID 绑定。复核新 `public_beating_pattern_types` 对合法天王炸的即时应手牌型结果，必要时补最小测试，不改规则真值或 Botzone 协议。
2. 在修复后的默认 Botzone factory 禁网 Request 中确认：有界记牌信息仍出现；候选对照两端确实在最终展示候选内，推荐闭环且最终候选不超过 80；fake transport 返回展示原始 ID 时 `source=model`。不加成功模型后的策略改牌。
3. 用完整、可复现的合法牌局选最多四个代表状态做改前/改后同状态比较，覆盖四人记牌、多人残局未知归属、唯一归属的 1v1，以及“连对与小单”取舍和相反条件。所有者的 `445566` 描述只能作为近似场景，不能称为现场复原。冻结每个状态的公开事实及合法动作，比较 baseline `5d5fa5b` 与本次修复版各自实际展示的候选、记牌内容和模型选择；场景不足四个时按实际可解释样本运行，不为凑配额增加请求。
4. 在一个明确的 M3 评测任务内，真实 DeepSeek 最多 **8 次**（最多四对）、零重试、两版均用所有者指定的 `deepseek-flash`。用进程范围环境覆盖 `DEEPSEEK_MODEL` 并经 `config.py` 取配置；不读写 `.env` 或输出密钥/端点/完整 prompt/模型自由文本。`config.py` 的 `deepseek_enabled=false` 不自动阻止显式 DeepSeek factory，人工批次也已有自己的模型覆盖；不要仅因评测父进程读到 `deepseek-v4-flash` 或该布尔值而再次空转。若缺少必要凭据、提供方拒绝模型或网络不可用，就停止外部请求、保留禁网结果并说明实际发送次数，不擅改模型或重试。
5. 记录每对候选可见性、模型返回原始 ID/牌型、合法性、`source`、选择是否变化和必要的条件性残局对照。具体牌局的选择变化及 RuleBased 续局只提供方向性证据，不宣称总体胜率改善；若模型选择相同也如实记录，并交回规划决定下一步。

运行直接相关测试、主规则回归和全量 `python -m unittest discover -q`，`git diff --check`。只按精确路径提交本任务自有业务代码/tests；报告修复证据、评测结果与限制、真实请求数、commit 和最终 Git 状态。
