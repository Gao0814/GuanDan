# Coding Codex 执行 Prompt：修复连续 Botzone 批次启动闪退

## 事实与目标

项目所有者实际运行 `scripts/run_manual_botzone_batch.cmd` 后，CMD 窗口一闪而逝，Botzone 页面没有显示“已连接”。这发生在开局之前，不能改写成中途停牌或断言 DeepSeek 超时。规划只读确认：新 `.cmd` 在 Python 退出后立即 `exit /b`，旧单局 `.cmd` 则默认等待按键；`cmd /c scripts\run_manual_botzone_batch.cmd --help`、当前 connector 进程探测及固定 workspace 根路径检查均通过，当前固定 workspace 没有新 `manual-batch-*` 子目录。它们不能确定所有者启动当时的具体错误类别。

交付一个**双击能看清失败原因、正常启动后持续轮询**的所有者自启入口。保持默认最多 10 局且可改：同一个前台 DeepSeek connector 在等待建桌、idle poll、两局之间持续运行，不逐局暂停或重启；只有达到目标局数、所有者明确 Ctrl+C/等效中止，或可报告的真实故障/明确配置上限，才结束。页面建桌和 connector 的真实启动/停止仍由所有者完成；Coding 本任务不得运行真实 Botzone connector、DeepSeek 请求或浏览器。

## 实现边界

先读 `AGENTS.md`、项目 Skills 清单、`README.md`、`CLAUDE.md`、`docs/PROJECT_STATUS.md` 顶部、`docs/PLAN.md` 顶部、`docs/INVARIANTS.md`、`docs/CODING_BOUNDARY.md`，查 Git status/diff/HEAD。重点核查新旧 `.cmd`、`integrations/botzone/manual_batch.py` 的进程探测、workspace 创建、预检、子进程等待与退出路径，`runner.py` 的 idle/target/limit 行为及对应测试。项目 Botzone live Skill 只适用于 Codex 监督真实对局，本任务不执行现场；不触发 workspace 回收 Skill。

1. 在保留真实退出码的前提下，复用旧单局入口的窗口体验：双击时，预检失败、连接器立即退出和正常达到目标后，窗口都显示固定低敏结果并等待用户关闭；从已有终端调用可通过明确 `--no-pause` 参数关闭等待，避免脚本无法自动化。`--no-pause` 不能误传给 Python 业务参数。不要输出 URL、密钥、prompt、模型响应或原始异常正文。
2. 先用禁网 fake 进程/路径检查复现早退各边界，定位当前真实可证明的缺口并最小修复。至少区分：进程占用检查失败、workspace 准备失败、零网络预检失败、connector 启动后立即退出、运行中达到目标、用户中止。若所有者这次的精确早退原因无法从保留证据确定，明确报告未知，不靠静默重试或绕过配置/协议失败制造“已连接”。在固定 workspace 只创建全新批次子目录，不改变写入根目录，不碰旧 evidence 或个人 workspace。
3. 验证 `subprocess.run` 所启动的**唯一前台 connector**在无新桌的 idle poll 后仍保持运行，并在一局完赛、目标尚未达到时继续轮询下一局。需要的运行上限应足以覆盖所有者手工连续十局，且退出时说明是目标、用户中止、上限还是故障。保持 `--agent deepseek`、进程级 `deepseek-flash`、119 秒决策期限、stage trace、逐局低敏结果、聚合 audit 和 ACK 事务现状；不改算法、模型超时策略、动作选择或成功模型后的结果。

## 验收与交付

- 禁网覆盖双击与命令行两种入口的可见结果、退出码与 `--no-pause`；fake transport 覆盖 idle → 第一局完赛 → idle → 第二局完赛、默认/自定义目标、Ctrl+C/等效中止、失败分类和旧证据保持原样。相关测试、主规则回归、适用全量测试与 `git diff --check` 通过。不要为了测试启动实际连接器或运行联网 preflight。
- 只提交本轮自有脚本、必要的批次启动逻辑及 tests，不改 `engine/`、算法策略、`.env`、规划 docs、封板标签或 workspace 旧证据。给所有者一条可复制的双击/命令行使用说明：窗口中何时仍在等待连接、何时页面确认“已连接”后再建桌、如何手动停止，以及若再早退应保留哪个新批次目录并提供哪个固定错误类别。
- 报告已证实的闪退原因与尚未证实的部分、真实 Botzone/DeepSeek 请求数（本任务应为 `0`）、验证、commit 和最终 Git status。不得把禁网通过写成已完成现场连接验收；真实页面连接由所有者后续确认。
