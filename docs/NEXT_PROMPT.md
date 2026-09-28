# 下一项 Coding 任务：M3d 收回记牌资源计算的本地时延

你是 Coding Codex。先读 `AGENTS.md`、适用项目 Skills、`README.md`、`CLAUDE.md`、`docs/PROJECT_STATUS.md`/`docs/PLAN.md` 顶部、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`；检查 Git status/diff/HEAD、`b8e40a8`、`agents/card_tracker.py`、`engine/rules.py`、默认 Botzone factory 与相关 tests。规划已独立确认 M3c 的输入区分度，也在同机禁网发现 seed `0/1` 的 80/39 候选记牌组装由上一版约 `0.084/0.062s` 增至 `6.401/3.497s`；简化 factory 整次 fake 调用约 `6.652/3.576s`。这段时间占用从 play 请求到达起计的 119 秒决策预算。本任务直接优化这条算法计算路径，不拆成独立诊断阶段。

## 改动目标

1. 让同一公开观察下的应手资源生成结果在多个候选间复用。当前 `public_beating_response_resource_counts` 对每个领出动作重枚举同一牌域中的单、对、炸弹和同花顺实体组合；可在引擎只读接口内建立按公开牌域与玩家容量限定的应手资源目录，再按合法比较规则回答不同领出动作。选用其他等价实现也可，但规则生成、逢人配声明与 `can_beat` 真值仍属于 `engine/`。缓存只在当前 observation/调用中有效，不得跨局面复用过期牌池，也不得碰隐藏手牌。
2. 记牌器对每个候选只建立一次逐家应手画像和余牌结构，再用于两两对照排序及最终最多两组文字。避免为 80 项候选的每一对重复执行规则枚举/字符串构造。保留 M3c 的公开资源档位、实体承载去重、逐家容量、行动顺序和推荐优先级；不通过缩减实际候选、删掉应手类别或提前返回 E0 换速度。
3. DeepSeek 继续在实际展示的原始合法候选中作最终选择；M3 引用 ID、推荐与最多 80 候选闭环，成功模型返回的 ID 与 `source=model` 不变。不改 connector、ACK、超时、`.env`、工作目录或现场日志。

## 验收

- 在完整引擎合法状态上比较 `b8e40a8` 与优化版的公开资源档位、逐家不能接/可能/确认、最多两组对照及其端点。至少覆盖 seed `0/1` 起局、容量为 3 的排除局、E2 唯一手牌和一例历史更新后的第二次观察；包括自然/配牌炸弹、同花顺与天王炸。若文字排序因等价结果不同而变化，解释差异，不能只比摘要长度。
- 禁网默认 Botzone factory/fake transport 核对真实最终候选、推荐与 M3 引用、原始 ID 和 `source=model`。对 seed `0/1` 在同机冷运行多次并报告候选数、记牌摘要与整次 fake 选牌耗时的前后分布；目标是把 seed `0` 的约 6.4 秒缩到约 2 秒以内、seed `1` 的约 3.5 秒大幅缩短。计时只作报告，不写依赖机器速度的断言；若未达到目标，给出实际瓶颈，不靠放宽截止时间掩盖。
- 运行定向测试、引擎主规则回归、全量 `python -m unittest discover -q`、`git diff --check`。只按精确路径提交本轮业务代码/tests，交回修改、前后耗时、正确性证据、当前范围内剩余风险、commit 与最终 Git 状态。本任务不重复真实 DeepSeek 请求，也不运行 Botzone/connector/browser；M3c 的四次真实选择已足够说明当前小样本证据边界。
