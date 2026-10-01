# Botzone 当前接入说明

本文件保留现役接口和运行边界，旧L阶段、capacity预注册和逐轮报告已由Git历史保存。使用步骤以[README.md](../README.md)、根AGENTS及适用项目Skill为准。

## 运行链

`integrations/botzone`负责长轮询、协议与实体ID映射、公开payload重建、原始合法动作验证以及响应/ACK事务；`agents`只从引擎合法ID中选择。显式选择DeepSeek路径，默认rule不能当模型运行证据。模型配置经config/环境读取，凭据不进入源码、日志或共享报告。

所有者的连续试局入口为`scripts/run_manual_botzone_batch.cmd`；`--games N`是跨启动最近N局证据容量，不是自动结束局数。所有者自行启停、网页建桌与开始。轻量入口为`scripts/run_manual_botzone.cmd`，默认个人GuanDanManualWorkspace；固定批次用BotzoneWorkspace。两个connector不能同端点同时轮询。

当前仅级牌2、四人、无需进贡的单局。官方牌型/双下时机与项目规则胜平负的差别见[BOTZONE_RULE_ALIGNMENT.md](BOTZONE_RULE_ALIGNMENT.md)、[BOTZONE_REFEREE_EXCERPTS.md](BOTZONE_REFEREE_EXCERPTS.md)。平台积分1/2/3另列，不覆盖规则draw或搜索目标。

## 私有证据与审计

固定批次按本地时间分局留证，最近N局有界滚动；models/request/body仅在所有者批准的固定私有诊断链保存，不输出或共享。request_prepared不证明送达，pending不冒充ACK。记录不包含密钥、连接URL/Cookie、原始模型自由文本或异常正文。已观察历史不自动称完整裁判牌谱；未知其他暗牌与双下个人名次不补造。

Codex监督单局需要完整读取[botzone-manual-live Skill](../.agents/skills/botzone-manual-live/SKILL.md)，遵守准备就绪→connector持续→页面已连接→配置核对→开始顺序。普通准备错误可修正，不继承旧正式实验整批作废门槛。所有者自操作无需照搬Codex托管流程。

固定workspace旧证据回收属于独立任务，必须读取[botzone-workspace-recycle Skill](../.agents/skills/botzone-workspace-recycle/SKILL.md)并限定已审计精确清单；不在live期间清理。本轮项目精简没有操作固定workspace。

## 验证与后续

按改动选择协议、adapter、期限、runtime、留证/ACK等直接受影响测试，不因连接器目录变化自动全量或真实建桌。现场少量胜负可作方向性观察，真实胜率收益需要共同条件和合理配对；当前四版本比较尚未开始。
