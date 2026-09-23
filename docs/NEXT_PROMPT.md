# Coding Codex 执行 Prompt

任务：H3-A9——在与 H3-A8 不重叠的完整单局状态上，预先固定新队列并运行一次小规模真实 DeepSeek 同状态动作质量代理。H3-A8 六个冻结状态得到 3 `selected_better`、3 `tie`，只是 RuleBased 续局下的单点代理；本任务检验该观察是否在独立状态上仍成立，不改生产策略，不声称胜率或因果收益。

## 边界与预注册抽样

1. 阅读适用 `AGENTS.md`、检查 `.agents/skills/`，并阅读 `README.md`、`CLAUDE.md`、`docs/CLEAN_HANDOFF.md`、`docs/PROJECT_STATUS.md`、`docs/PLAN.md`、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`、`evaluation/action_quality_proxy.py`、`evaluation/h3_model_probe_fixtures.py`、相关测试及 `config.py`。核对 Git status、diff、HEAD 与最近提交；HEAD 须包含 `4547f7decb84d2a6bdb1588d1d48957f5b9f46ce`，保留他人修改。
2. 只在 `evaluation/` 与对应 `tests/` 新增最小的新队列构造和测试，复用 H3-A7a 的真实客户端请求绑定、RuleBased 参考、同快照双分支续局与质量比较；不改原六样本、`engine/`、生产 `agents/`、RAG、prompt、Botzone、配置或规划 docs。不新增模型后置动作覆盖、依赖或现场牌面特判。
3. 新队列固定为六个状态：2 个 opening、2 个 midgame、2 个公开 endgame 族状态。仅用独立 seed `920..959`；依 opening→midgame→endgame 族顺序填充，每层按 seed 升序、局内 step 升序选最早满足资格的状态，已占用 seed 跳过。六项必须来自六个不同 seed，公开状态/完整动作签名不得与 H3-A8 样本重复。每局从完整 108 张、四家各 27 张、级牌 2、无贡起步，后续仅通过引擎合法动作与冻结 RuleBased 回放。资格仅依据模型调用前可知事实：轮到玩家 1、至少两个非 pass canonical 动作、真实禁网客户端进入模型路径、最终候选至少 2 且不超过 80、RuleBased 参考动作在最终候选、请求体/候选/source 闭环。不得看到模型输出后替换、补采或改变抽样顺序；若固定范围不足六项，零真实请求停止并报告阶段，不扩大 seed 范围。

## 离线门槛与真实请求

1. 先实现并锁定上述抽样的纯离线回归：真实公开 observation 与完整 canonical 动作一致、初始实体牌守恒、各层及 seed 不重复、最终候选和 Request 正文绑定、禁网 fake transport 一次调用、六组本地双分支续局完成、低敏结果稳定。运行相关测试、主规则回归与 `python -m unittest discover -q`；检查 `git diff --check` 和完整 diff。资格全数通过后只按明确路径提交本轮自有评测代码/tests；提交后再次核对 HEAD、Git clean 与同六项资格。任一门槛失败则不发真实请求。
2. 真实 DeepSeek 请求上限为 6，每样本至多 1 次，重试 0；严格少于 10 次的长期授权适用。只从 `config.py` 读取运行时凭据/endpoint，本进程强制 `max_retries=0`；通过 H3-A7a 的 transport 接口调用生产客户端，不另造 prompt 或第二条模型调用。原始响应 ID、客户端返回 ID、实际最终候选、`model` source 和续局首步必须守恒。任一技术失败、超时、非法响应或续局 `unevaluable` 即停止后续请求，不补采、不重试，诚实保留部分结果。
3. 在仓库外既有普通目录 `D:\VsCodeProject\GuanDanH3A2Audit` 中独占新文件 `h3-a9.jsonl`；只读确认父目录非链接、目标不存在，绝不覆盖。网络前同步写 header、六条 qualification 与 `qualification_complete`；每次请求前同步写 `request_started`，请求后同步写 `request_result`，结束时同步写 summary（含提前停止）。只允许低基数样本名/phase、候选数、固定状态码、团队终局类别/名次和/步数、比较类别与请求/重试计数。不得持久化或输出手牌、具体 action ID、prompt、模型文本/reasoning、密钥、URL、Cookie 或异常正文。完成后只读重开并核验事件顺序、配对、计数、schema、大小和 SHA-256；本地 ledger 不是网络侧独立计数证据。
4. 不运行 Botzone/live/connector/browser/preflight，不访问 `D:\VsCodeProject\BotzoneWorkspace`、seed `47004` evidence、旧 H3 ledger 或系统 Temp 文件。报告提交、六项低敏 phase/候选数/来源 seed 的非敏感标识、离线测试数、真实请求/重试数、逐项比较与汇总、ledger 身份及最终 Git status。不得将 H3-A8 与本轮的合计代理结果称为胜率、策略真值或生产改动依据；留待规划 Codex 独立复审再决定下一步。
