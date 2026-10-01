# 在原目录去重融合并回收已退役代码

你是Coding Codex，工作目录固定D:\VsCodeProject\GuanDan，继续当前cao分支。所有者明确要求直接在原项目更新，不再维持GuanDanMerged_10-1；备份10-1.v1可复原，并授权核对后把不再需要的项目文件放回收站。Planning负责docs和外部自有副本/备份清理，Coding负责业务、tests及非docs文件。不得改Planning docs或提交对方修改。

先读AGENTS、适用Skills、CLEAN_HANDOFF/PROJECT_STATUS/PLAN顶部、INVARIANTS/CODING_BOUNDARY及此Prompt。核对原目录与融合目录Git status/HEAD。原目录业务仍为10-1.v1（8d6a257，M10业务5d31bd1）；融合副本业务fbdfa7e，最新16edb6b。原始10-1.v1.tag/bundle已验证；不读取.env/画像/私有现场正文，不启停connector，不作真实外部请求。

## 机制目标

原项目card_belief已逐家记录played_cards和pass_count，card_tracker已有守恒、未见牌池、行动顺序、候选应手与pass软证据，deepseek_client已有队友控桌/紧迫性/资源净得失，M9/M10已完成。此前融合新增PlayerBehavior等重新遍历统计和单独提示块，没有策略收益证据；不能因为来源不同就当新能力保留。

1. 把fbdfa7e的能力与原项目实际模型输入逐项比对，按需要只取真正缺少且可表达的增量，直接修改GuanDan。保留10-1.v1，不复制整个目录/.git/.env/.venv。可只读取副本commit或git fetch其commit以保存候选实现历史；不要把副本docs混入业务提交。无需机械cherry-pick后再撤销冗余。
2. 去掉重复的每家pass/出牌统计、未证明有决策价值的均值/早炸次数、第二套历史遍历和重复牌权/紧迫性提示。优先复用既有结构和渲染，不维持一整套teammate_fusion模块/开关来包装已有能力。若所有现有提示都已覆盖，可以不新增任何融合业务模块，明确报告来源审查无可确认增量，不为“合并”凑代码。若头游双下等确有缺口，按正确finish_order/在局顺序补到已有合适位置，仅引用最终展示原始canonical ID；不能用固定seed/牌点/ID或成功模型后置改牌。
3. 主动清理已完成用途的非docs历史代码/旧阶段评测与一次性测试/生成物：从archive_legacy及evaluation旧冻结/ablation/proxy入口核对引用、现有入口和测试helper依赖，按闭包回收已退役部分。保留在用主线模块、未来公平策略比较必要通用接口及能发现实际回归的测试；测试多/文件旧不是删除理由，不能只因不在生产import就删除全部测试。若retired评测只被它自己的测试引用，可同步回收这一套；被现役测试复用的fixture/helper必须保留或用最小合理替代。不要删除失败测试掩盖问题。
4. 将精确核对可退役的文件/目录发送Windows回收站，先确认绝对路径归属GuanDan、没有链接/重解析子项、目录仅含批准内容；单一PowerShell/.NET端到端，不用rm -rf/git clean。可用Microsoft.VisualBasic.FileIO.FileSystem.DeleteFile/DeleteDirectory(...,OnlyErrorDialogs,SendToRecycleBin)。未纳Git的.env/.venv/日志/运行证据不受Git恢复保护，保持原样；外部副本、D盘备份、队友输入与Botzone目录由Planning处理，不操作。

## 验证与提交

完整差异、剩余import/引用闭包与现役入口核对；编译检查可内存compile不额外留脚本。按实际变动只选少量相关测试或已有factory禁网fake调用验证原合法ID/source和M9/M10保持。不跑默认全量，不重做旧算法审计，不调用真实模型。清理列表需要每组用途/引用依据、回收方式和实际结果；无法确定不必要的文件先保留并报告具体依赖，不用为完成数量硬删。

按明确路径提交自有业务/tests/清理，不能git add .或处理Planning正在修改的docs。完成后报告：最终真正吸收了什么/去掉了哪些重复、回收路径及闭包依据、实际命令和结果、commit/status、当前范围真实剩余风险。给Planning低敏报告，不保存prompt/请求/模型自由文本。融合副本可在最后被Planning回收，先通知已保存必要业务commit/无未保存内容。
