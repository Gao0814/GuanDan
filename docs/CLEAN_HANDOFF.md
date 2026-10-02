# 当前项目交接

更新：2026-10-02。新对话读取根AGENTS、匹配Skill、本文件、PROJECT_STATUS/PLAN、INVARIANTS/CODING_BOUNDARY和存在的NEXT_PROMPT，核对真实Git；不从旧报告猜任务。

## 当前任务

业务HEAD为59814b1f66b334c00b7e6d0acae078b92c01412b，机制复审通过；后续只有Planning文档。本次开始于干净cao、51b7abcd18948231f9d64461065d3233efda8662。当前有新的[NEXT_PROMPT.md](NEXT_PROMPT.md)：冻结四手普通跟牌，A原请求/B仅恢复新增摘要前既有记牌内容，8次Flash无重试的消融诊断；不先改业务、tests、RAG、候选或模型选择器，不重打实战。

用户确认今晚五把100207_0至100211_0全部不同seed；比较今天较早五把。平台正分3/5→1/5，项目规则可确认胜局1/5→0/5，部分规则负/平未完整留存，不造终局名次。最近119动作全部ACK闭环，73请求/72模型成功同次reason，一次100211决策3超时规则回退；全部Flash/temperature0/streamtrue。新增跟牌摘要36/73，M10为10/73、M9正文1/73；近期正文并未普遍增加。运行Git SHA没有留证，不能由当前HEAD冒称每局版本。

重点原决策、完整成本/解释核对及十局映射见[PROJECT_STATUS.md](PROJECT_STATUS.md)。100211开局ID134自然34567拆两组四炸及对7，reason自述低顺减张/留控制，未解释成本；实际请求完整支付仅展开另一顺子，且无新增跟牌摘要/M9/M10。100209决策2/3的reason确实保留了另一些控制/同花顺资源，但未比较损掉9炸、级牌组及三5的代价；不能把共有保牌优点当选中动作优越的证明。100210决策5/9拆三Q/三K出单，reason保留其他资源与实物核对。四个跟牌输入消费新增摘要、无M9/M10，适合消融；不要把开局缺口同时修进本轮比较。

最近十局都finished且evidence_incomplete=false，目录不得改写/清理。当前请所有者暂缓新局，保留滚动边缘的比较证据至诊断交回；Codex不启停connector或改保留状态。同日下一新有效局100212，不要求重打任何seed；同seed尝试从_0起、只计一有效单位，局名不倒填历史seed。具体路径都在固定D:\VsCodeProject\BotzoneWorkspace\games，不复制请求或原reason到仓库/报告。

## 已验收与保留待办

59814b1完整固定承载绑定分类、cc04fa3联合自然/通配支付及e007bbf普通跟牌投影通过机制验收。保留250毫秒/45000工作量/1350字符及异常/超长整块回旧摘要；84次canonical与Planning30次分类参照、两类factory原ID闭环支持事实正确性，不证明代表覆盖全候选或策略改善。旧四组8次诊断没有一致改善；缺失完整reason语义的旧诊断不补造/追加请求。旧特定RAG标题断言父版本亦失败，保留未算通过。

A历史pass3c81f66/c02db61、B携带81ab389、末组b30ce1d、残牌/双经验77d8d34、协同9646c2f、短reason369e873均已验收，不重新实现。短reason真实试局写盘已确认，按编号/原ID/pending→ACK核对；无长reasoning/完整响应落盘或旧记录追填。RAG最多两条并非每次两条，资源正文共享300字符可能整条省略；本次实战确认最近全部请求只有一条，但不能据数量直接证明退步。详尽性待办保留，优先内容与相关性，不上工具/动态文件架构。

M9共享推进8bf58ed及此前目录缓存/双指标饱和完成验收，本阶段性能收口。原23完整约173毫秒但默认不完成，24边界稳定性未证；不再写成下一项自动优化。35毫秒/5000节点、公开确证/完整双指标、未完成撤回及M10共同假设边界保持，见[M10_REVIEW.md](M10_REVIEW.md)。规则c80ea27、M10 5d31bd1及融合回收bf712a9已完成；四版本比较未开始，先等双方冻结入口。

## 工作与恢复

继续D:\VsCodeProject\GuanDan/cao，Coding负责业务/tests及任务直接文件，Planning只AGENTS/Skills/docs，分别按明确路径提交，未跑全量不构成验收失败。最近游戏任务使用[botzone-game-audit](../.agents/skills/botzone-game-audit/SKILL.md)，普通代码复审不加载live/回收Skill；当前无实时托管或清理任务。

10-1.v1=8d6a2579ea4eca0917d8a0ce49aaf8c8545c22fc，完整历史D:\VsCodeProject\GuanDan_10-1.v1.bundle及同目录说明/SHA已验证保留。融合副本已回收，历史在codex/merge-teammate；不建常驻工程副本，不从旧Prompt再合并。Git不恢复私有.env/.venv/日志/现场；这些保持原样。维护记录见[MAINTENANCE_REPORT.md](MAINTENANCE_REPORT.md)。

本次Planning真实POST0，无业务修改、配置读取、原证据改写、现场/网页或回收操作。消融后独立复审是否收缩新增摘要或修正成本/RAG覆盖，不能直接由五局下降确定回退整个项目。
