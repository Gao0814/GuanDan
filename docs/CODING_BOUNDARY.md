# CODING_BOUNDARY

## 1. 文档目的

本文件用于约束当前阶段允许修改什么、不得越界做什么、以及实现时必须遵守的边界。

当前阶段的唯一主目标是：

> 在现有项目基础上，完成“单局掼蛋核心规则 + AI 只在合法动作中选 `action_id`”的闭环实现。

本阶段不是多局比赛平台建设阶段，也不是强化学习 / 自博弈 / 比赛制扩展阶段。

---

## 2. 当前阶段项目根目录约定

当前阶段项目根目录应采用以下约定：

- `.venv/`：本地 Python 虚拟环境目录
- `.env`：本地环境变量文件，保存运行时私密配置
- `.env.example`：环境变量模板文件，不包含真实密钥
- `config.py`：统一读取环境变量的配置入口

说明：

- `.venv/` 是本地开发环境产物，不属于项目源码逻辑
- `.env` 属于本地私密配置，不应提交真实内容
- 不使用 `env/` 作为目录名，以避免与虚拟环境混淆

---

## 3. 推荐文件树

项目当前阶段推荐以以下结构为准：

```text
project/
├── .env
├── .env.example
├── .gitignore
├── .venv/
│
├── docs/
│   ├── SPEC.md
│   ├── PLAN.md
│   ├── TESTS.md
│   ├── INVARIANTS.md
│   ├── RAG_KB.md
│   └── CODING_BOUNDARY.md
│
├── engine/
│   ├── __init__.py
│   ├── cards.py
│   ├── patterns.py
│   ├── actions.py
│   ├── state.py
│   ├── rules.py
│   ├── game.py
│   └── logging_utils.py
│
├── agents/
│   ├── __init__.py
│   ├── base.py
│   ├── rule_based_ai.py
│   ├── rag_advisor.py
│   └── decision_trace.py
│
├── rag/
│   ├── __init__.py
│   ├── kb_loader.py
│   ├── retriever.py
│   ├── rule_corpus/
│   │   └── guandan_rules.md
│   └── experience_corpus/
│       └── basic_human_experience.md
│
├── cli/
│   ├── __init__.py
│   ├── run_4ai_debug.py
│   └── run_4ai_debug.py
│
├── tests/
│   ├── __init__.py
│   ├── test_patterns.py
│   ├── test_rules.py
│   ├── test_game_flow.py
│   └── archive_legacy/
│
├── logs/
│   └── .gitkeep
│
├── config.py
├── requirements.txt
└── README.md
```

说明：

- 若仓库中存在历史文件，不要求本轮删除
- 但本轮实现范围应优先收敛到上面这些核心目录与文件
- 历史比赛层 / 多局层 / 额外实验文件，若与本轮目标无关，不应顺手扩改

---

## 4. 当前阶段允许修改的目录与文件

### 4.1 文档对齐阶段允许修改

在“先文档对齐”阶段，允许修改：

- `docs/SPEC.md`
- `docs/PLAN.md`
- `docs/TESTS.md`
- `docs/INVARIANTS.md`
- `docs/RAG_KB.md`
- `docs/CODING_BOUNDARY.md`

### 4.2 测试与实现阶段主要允许修改

在“补测试 + 最小实现”阶段，主要允许修改：

- `engine/cards.py`
- `engine/patterns.py`
- `engine/actions.py`
- `engine/rules.py`
- `engine/game.py`
- `engine/logging_utils.py`
- `agents/base.py`
- `agents/rule_based_ai.py`
- `agents/rag_advisor.py`
- `cli/run_4ai_debug.py`
- `tests/test_patterns.py`
- `tests/test_rules.py`
- `tests/test_game_flow.py`
- `archive_legacy/tests/test_rule_based_ai.py`
- `archive_legacy/tests/test_rag_constraints.py`
- `archive_legacy/tests/test_cli_debug_output.py`
- `rag/kb_loader.py`
- `rag/rule_corpus/guandan_rules.md`
- `rag/experience_corpus/basic_human_experience.md`
- `config.py`
- `.env.example`
- `README.md`
- `requirements.txt`

### 4.3 有条件允许修改

以下内容仅在与本轮主目标直接相关时允许最小改动：

- `engine/state.py`
- 其他测试辅助文件
- 其他 CLI 输出辅助文件

前提是：

- 该修改是为了支撑单局核心规则闭环
- 该修改无法通过更小范围替代完成
- 不得借机做无关重构

---

## 5. 当前阶段不允许扩展的范围

以下内容不属于当前阶段目标，不得主动扩展实现：

- 多局升级赛完整规则
- 打到 A 的长期比赛胜利条件
- 复杂贡还 / 抗贡比赛制
- 完整地方规则百科
- 强化学习
- 自主学习
- MCTS
- 蒙特卡洛优化
- 自博弈训练
- 高级前端
- 复杂部署系统
- 第二阶段或第三阶段功能

说明：

- 若仓库中已有历史相关代码，本轮也不以扩展这些内容为目标
- 除非本轮实现被现有依赖阻塞，否则不应进入这些模块

---

## 6. 架构边界

Codex / Copilot / 其他实现代理在本阶段必须遵守以下架构约束：

1. 规则引擎与 AI 决策分离
2. 合法动作生成器是动作唯一入口
3. 规则引擎是动作合法性与状态更新的最终裁判
4. AI 只能从合法动作集合中选择动作
5. RAG 只能提供规则与经验知识，不能直接执行动作
6. 任何非法动作不得进入状态转移
7. 配置读取必须集中在 `config.py`
8. API 密钥和 URL 不得写死在代码中

---

## 7. 动作与规则实现边界

本轮实现必须满足：

### 7.1 Action 边界

`legal_actions()` 返回的每个动作至少包含：

- `action_id`
- `declared_pattern`
- `declared_cards`
- `carrier_cards`
- `wildcard_count`
- `wildcard_info`
- `display_text`

### 7.2 规则边界

引擎必须负责：

- 牌型识别
- 合法动作显式展开
- 跟牌压制判断
- 炸弹 / 同花顺 / 天王炸层级比较
- 接风
- 名次推进
- 三游终局
- 平局 / 胜负判定

AI 不得负责：

- 牌型识别
- 动作合法性判断
- 压制比较
- 状态推进
- 逢人配替代推导

### 7.3 逢人配边界

- 逢人配 = 红桃级牌
- 一手动作中最多使用 1 张
- 只能参与非王类牌型
- 一旦声明替代，就按声明后的牌参与比较
- 不能给 AI 留“模糊解释空间”

---

## 8. 关于 `.venv` 的约束

`.venv/` 的作用仅限于本地 Python 虚拟环境。

要求：

- `.venv/` 不属于项目源码
- `.venv/` 不应写入业务代码
- `.venv/` 不应提交到 Git
- Codex 不应在 `.venv/` 下创建、修改、移动任何项目逻辑文件

---

## 9. 关于 `.env` 的约束

`.env` 用于保存本地私密运行配置，例如：

- `DEEPSEEK_API_KEY`
- `DEEPSEEK_BASE_URL`
- `DEEPSEEK_MODEL`
- `DEBUG`

要求：

- `.env` 中可以保存 DeepSeek API key 和 base URL
- `.env` 不应提交真实内容到仓库
- Codex 不得伪造或写入真实密钥
- Codex 只能依据 `.env.example` 约定环境变量名
- 代码中不得写死 API key、base URL 或模型名

---

## 10. 关于 `.env.example` 的约束

`.env.example` 用于声明项目运行所需环境变量，但不得包含真实密钥。

推荐至少包含：

- `DEEPSEEK_API_KEY=`
- `DEEPSEEK_BASE_URL=https://api.deepseek.com`
- `DEEPSEEK_MODEL=deepseek-chat`
- `DEBUG=true`

Codex 可以创建或修改 `.env.example`，但只能写模板值，不能写真实敏感信息。

---

## 11. 关于 `config.py` 的约束

`config.py` 是项目中唯一推荐的环境变量读取入口。

要求：

- 统一读取 `.env` 中的运行配置
- 各模块不得分散、重复、随意读取环境变量
- DeepSeek API 相关配置应通过 `config.py` 暴露
- `rag/` 与 `agents/` 中需要使用配置时，应从 `config.py` 获取

`config.py` 不应承担：

- 业务规则判断
- RAG 检索逻辑
- AI 决策逻辑
- 状态转移逻辑

---

## 12. 实现约束

- 使用 Python 3.11
- 优先使用标准库
- 不得猜测不存在的 API
- 不得引入无关第三方依赖
- 不得顺手重构无关代码
- 不得扩大需求范围
- 不得生成与当前文件树无关的复杂目录结构
- 不得创建 `env/` 目录来存放配置

---

## 13. 输出约束

每次实现代理输出代码时，必须同时说明：

1. 修改了哪些文件
2. 为什么修改这些文件
3. 是否涉及 `.env.example` 或 `config.py`
4. 是否依赖环境变量
5. 覆盖了哪些当前步骤目标
6. 还未完成哪些内容
7. 是否存在与 `docs/SPEC.md` 的冲突

---

## 14. 测试约束

实现每个步骤时，必须优先补充或更新对应测试。

没有测试支撑的功能，不应视为完成。

如果新增了配置读取逻辑，还应至少验证：

- 缺失必要环境变量时有明确错误
- 默认值行为明确
- 不依赖写死密钥

如果新增或修改了规则逻辑，还必须同步验证：

- 牌型识别
- 合法动作生成
- 压制比较
- 状态推进
- 终局 / 胜负判定

---

## 15. 本轮推荐实施顺序

当前阶段推荐顺序固定为：

1. 先改 `docs/*.md`
2. 再补 `tests/*.py`
3. 再最小修改 `engine/*.py`
4. 再校正 `agents/`、`rag/`、`cli/`
5. 最后做回归测试

未经明确指令，不应跳过测试直接大改实现。
