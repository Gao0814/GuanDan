# Coding Codex 执行 Prompt：个人 Botzone 单局异常只读复审

仅当项目所有者使用当前版本的 `scripts/run_manual_botzone.cmd` 完成一局个人试测、明确报告异常并停止下一次个人启动时执行。若该局没有异常，本 Prompt 不需要执行，也不要为了它额外建桌。先阅读根及适用范围内的 `AGENTS.md`、匹配的项目 Skill、`docs/PROJECT_STATUS.md` 顶部、`docs/INVARIANTS.md`、`README.md`；检查 Git status/diff/HEAD，确认包含 `d0cd02b`。这是只读诊断，不修改或提交业务代码、tests、docs、配置、workspace 或外部文件。

只访问个人固定目录 `D:\VsCodeProject\GuanDanManualWorkspace`，不要访问或清理 Codex 固定 workspace。先核对目录归属标记、普通非链接属性、允许的文件清单和无运行中的项目 connector；不满足即停止并报告，不搜索替代路径，不启动脚本以免轮换证据。不要读取 `.env`、输出连接 URL、密钥、prompt、模型文本或其他玩家暗牌。对当前个人试局的 audit、history、ACK trace 和 state 按实际存在情况只读核验类型、大小、哈希及 schema；需要读取内容时只提取低敏计数、阶段与时间线，不复述手牌或具体出牌。

按一次实际运行的证据逐层判定：页面/connector 是否连接、请求是否进入处理、DeepSeek 是否尝试与返回、原始合法 action ID 是否在实际候选内、响应是否完成 Header ACK、会话与 audit 是否守恒、终局分类是什么。若证据没有模型调用的分段时间，不要把长等待或 `platform_error` 推断为模型时延所致；普通长轮询 timeout 也不等于页面断连。区分已证实缺陷、仍未证实的假设和证据缺失。不要运行真实模型、第二桌、connector、浏览器或 preflight，也不要重试或清理。若定位到具体生产缺陷，给出一次最小 Coding 修复的文件和验收建议，交回规划 Codex 再派实现；若没有，就明确记录 `inconclusive`，不制造策略代码修改。报告最终 Git status 与任何保留的外部修改。
