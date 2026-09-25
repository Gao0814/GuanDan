# Coding Codex 执行 Prompt：一键个人 Botzone 试局与证据隔离

项目所有者已**暂停多牌型开局算法任务**，本次只实现他亲自运行的轻量 Botzone DeepSeek 试局入口。先读根 `AGENTS.md`、`.agents/skills/botzone-manual-live/SKILL.md` 的适用范围、`docs/PROJECT_STATUS.md` 顶部、`docs/CLEAN_HANDOFF.md` 顶部、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`、`README.md`，再只读核对 `integrations/botzone/__main__.py`、`runtime_config.py`、现有 audit/history/decision-trace 写入与相关测试。检查 Git status/diff/HEAD；不要混入他人修改。

交付一个 Windows PowerShell 单命令个人启动器（建议 `scripts/run_manual_botzone.ps1`，可选配最小纯函数辅助），并在 `README.md` 给出简短用法。项目所有者从仓库根目录运行一次命令后，脚本自动完成必要的零网络配置预检、启动**一个**前台 `--agent deepseek` connector；页面显示“已连接”后，所有者自行建一张四人、级牌 `2`、无需进贡的单局并点击开始。个人试局无需 Codex 实验的 seed 预注册、逐项哈希 inventory 或逐局人工报告；不运行 `--preflight-only` 代替真实连接，也不自动操作网页。真实 connector 的 URL/DeepSeek 凭据仍走现有私密配置，不输出或持久化。

个人工作根固定为 `D:\VsCodeProject\GuanDanManualWorkspace`，不得放入仓库、`D:\VsCodeProject\BotzoneWorkspace` 或任何其他 `Botzone*` 顶层目录。启动器须独立指定该根下的 state、audit、history、decision trace 等路径；默认保留足够让 Codex 事后复查异常的低敏/私有证据，但不保存 prompt、模型自由文本、密钥、连接 URL、Cookie 或响应正文。终端给出简短连接/结束提示；文件只留在个人根，不进入 Git。Codex 正式 workspace、seed `47005` 六份 evidence、旧 H3 ledger 和系统 Temp 全部不得读取、清理、覆盖或用作启动器的工作位置。

用户同意“无问题则下一局覆盖上一局；有问题则停止下一局并让 Codex 读取”。实现可恢复的自动轮换：新个人根不存在时创建带明确归属标记的目录；根已存在时，只有在解析后的**绝对路径精确等于上述个人根**、普通非链接、归属标记有效、内容均为启动器预期对象且没有运行中项目 connector 时，才将旧个人目录通过 Windows 回收站 API 移走并重建。不得用 `Remove-Item -Recurse`、通配删除、永久删除或仅凭名称前缀清理；未知文件、链接、目标漂移、回收失败都应原地停止并保留全部旧内容。尽可能在回收旧证据之前完成可做的无网络配置/命令预检。若所有者发现问题或请求复查，当前个人目录保持原样，Codex 可在该问题任务中只读访问；不要求用户提交每局报告。明确告诉用户：下一次个人启动会回收上次目录，因此报告问题后先不要重开。

独立目录只能隔离文件，不能隔离同一个 Botzone 本地 AI 端点。启动器应在开始前和真正启动前检查本机是否已有可归属项目 connector，命中则停止，且不要输出它的命令行或私密参数；README 提醒同一 Botzone 连接不能与 Codex 测试并行，跨主机并行无法靠本机进程检查保证。个人运行无需调用正式 `botzone-manual-live` 审计流程；但保持“先连接、后人工建桌/开始”、只有一个 connector、异常时保留证据等基本边界。推荐进程级设置 `DEEPSEEK_MAX_RETRIES=0` 并在退出后恢复；不要改变全局配置或 CLI 默认 `rule` 事实。

只改个人启动器、对应的离线测试/测试辅助及 README 最小用法；不要修改 engine、AI 策略、RAG、Botzone wire/session/runner 行为、`.env`、规划 docs 或项目 Skill。测试须在临时 scratch 目录和禁网/fake connector 下覆盖首次创建、第二次回收并重建、归属标记缺失/未知文件/链接/路径漂移/回收失败时 fail closed、运行中 connector 拒绝、URL/密钥不泄漏、审计路径仅指向个人根；不得在测试中触碰真实个人目录或 Codex workspace。做 PowerShell 语法检查、实际 CLI 参数只读核对、直接相关离线测试、`git diff --check`；纯脚本无法在当前环境完成的检查要诚实说明。**不要运行真实 preflight、connector、Botzone、浏览器、DeepSeek 或网络，不要创建真实个人工作根，也不要清理任何现存仓库外文件。**

只暂存提交自己的脚本、README 和相关测试，报告一条最终用户命令、覆盖/冻结规则、离线验证、commit、Git status、保留外部修改，以及个人目录仍未真实创建。不要宣称已完成一次现场连接或真实对局。此前多牌型开局 Prompt 保留在规划 commit `e054955` 的历史中，未获所有者恢复指令前不得执行。
