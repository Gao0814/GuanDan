# Coding Codex 执行 Prompt

任务：H3-A8——在已复审的六个完整对局状态上，独立运行一次低敏、同状态 DeepSeek 原始动作质量代理。H3-A7/H3-A7a 的固定样本、禁网真实客户端请求绑定和 RuleBased 双分支续局已经封板；本任务只采集六个单点模型动作并比较冻结续局结果，不修改生产策略，也不把代理结果称为真实胜率或最优打法。

## 前提与范围

1. 阅读适用 `AGENTS.md`、检查 `.agents/skills/`；阅读 `README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`、`evaluation/action_quality_proxy.py`、`evaluation/h3_model_probe_fixtures.py`、`config.py` 与相关测试。核对 Git status、diff、HEAD 和最近提交；HEAD 须包含 `6e304dc1afa4294431894837d0e138deb9de9727`，保留他人修改。
2. 固定现有六个样本及其顺序：两项 opening、两项 midgame、endgame 与 near_open_endgame；固定当前的完整/最终候选数 `53/21、83/50、6/6、6/6、9/9、8/4`。不得因模型选择、完成情况或胜负补采、换 seed、换参考动作、改续局规则或改质量比较口径。级牌 2、四人、无贡单局是既定项目范围。
3. 预注册真实 DeepSeek 请求上限为 6，每场至多一次、重试 0；项目所有者已长期授权单任务严格少于 10 次，不需另行申请。本任务不运行 Botzone/live/connector/browser/preflight，不访问 `D:\VsCodeProject\BotzoneWorkspace`、seed `47004` evidence、旧 H3 ledger 或系统 Temp 文件；不输出或持久化密钥、URL、prompt、手牌、动作 ID、模型自由文本、reasoning 或异常正文。

## 执行顺序

1. 先确认 Git clean，独立运行相关测试与主规则回归。以禁网 fake transport 从当前 HEAD 重建全部六个样本，核验完整 108 张起局、公开 observation/canonical 一致、phase 与候选数、参考动作可见、实际请求正文候选绑定、`model` source、六组续局完成。任一资格失败则零真实请求停止，报告固定失败阶段，不降低门槛。
2. 只从 `config.py` 读取运行时 DeepSeek 凭据和 endpoint，构造 `DeepSeekClientSettings`，本进程强制 `max_retries=0`；向评测器注入真实 `DeepSeekTransport`，复用 H3-A7a 的请求记录器和 `evaluate_quality_sample()`，不得另造 prompt、另发模型请求或通过假 provider 选动作。请求必须由同一公开样本和最终候选集生成；响应的原始 ID、客户端 ID、最终 ID、`model` source 与续局首步须在内存中守恒。任何技术绑定失败或 `unevaluable` 均禁止再发下一请求；不重试、不改样本，按实记录部分结果并停止。
3. 使用新的独占仓库外低敏 JSONL：`D:\VsCodeProject\GuanDanH3A2Audit\h3-a8.jsonl`。先只读确认目标不存在、父目录为普通非链接目录；不得覆盖旧文件或创建其它仓库外目录。网络前写入并同步 header、六条 qualification 与 `qualification_complete`；每次调用前同步写 `request_started`，调用后同步写 `request_result`，最后同步写 summary。即使提前停止，也写可审计的部分 summary；只允许样本名/phase、完整和最终候选数、固定 provider/绑定/续局状态码、团队终局类别/名次和/步数、`selected_better|reference_better|tie|unevaluable`、请求/重试计数及非敏感版本标识。不得持久化可还原牌局、具体动作或模型文本的字段。完成后只读重开 ledger，校验 schema、顺序、请求配对、计数守恒、文件大小与 SHA-256；不把本地 ledger 当作网络侧独立计数证据。
4. 报告逐场低敏代理结果及汇总：完成数、技术守恒数、三类比较数与 `unevaluable` 数；明确这是六个冻结状态、RuleBased 续局策略下的单点相对代理，不能与 H3-A6 的短手牌 fixture 当作同状态因果对照，也不能声称胜率收益。若仅部分请求成功，诚实保留 inconclusive/部分结果，不以其它 fixture 补齐。

不修改或提交仓库代码、tests、RAG、docs、配置或 `.env`；只创建上述 fresh ledger。报告定向/主规则测试计数、真实请求与重试数、ledger 路径/大小/SHA-256、最终 HEAD/status 和保留的外部修改。规划 Codex 将独立复核 ledger 与离线资格后再决定是否需要策略调整。
