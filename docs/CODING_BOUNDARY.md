# CODING_BOUNDARY

## 1. 项目根目录约定
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

## 2. 推荐文件树
项目当前阶段应以以下结构为准：

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
│   └── play_human_vs_ai.py
│
├── tests/
│   ├── __init__.py
│   ├── test_patterns.py
│   ├── test_actions.py
│   ├── test_rules.py
│   ├── test_state.py
│   ├── test_game_flow.py
│   ├── test_rule_based_ai.py
│   └── test_rag_constraints.py
│
├── logs/
│   └── .gitkeep
│
├── config.py
├── requirements.txt
└── README.md

---

## 3. 允许 Codex 编写或修改的目录与文件
当前阶段只允许在以下位置编写或修改代码：

- engine/
- agents/
- rag/
- cli/
- tests/
- logs/（仅限必要的日志输出支持，不写死业务逻辑）
- config.py
- README.md
- requirements.txt
- .env.example
- .gitignore
- docs/PLAN.md
- docs/TESTS.md

---

## 4. 不允许 Codex 修改的文件
以下文件是当前阶段的需求与约束基准，不允许擅自修改：

- docs/SPEC.md
- docs/INVARIANTS.md
- docs/RAG_KB.md
- docs/CODING_BOUNDARY.md

以下文件属于本地环境或私密配置，也不允许 Codex 擅自写入真实内容：

- .env
- .venv/ 中的任何文件

如果实现与这些文件发生冲突，Codex 只能报告冲突，不能直接改写。

---

## 5. 关于 .venv 的约束
`.venv/` 的作用仅限于本地 Python 虚拟环境。

要求：
- `.venv/` 不属于项目源码
- `.venv/` 不应写入业务代码
- `.venv/` 不应提交到 Git
- Codex 不应在 `.venv/` 下创建、修改、移动任何项目逻辑文件

---

## 6. 关于 .env 的约束
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

## 7. 关于 .env.example 的约束
`.env.example` 用于声明项目运行所需环境变量，但不得包含真实密钥。

推荐至少包含：

- `DEEPSEEK_API_KEY=`
- `DEEPSEEK_BASE_URL=https://api.deepseek.com`
- `DEEPSEEK_MODEL=deepseek-chat`
- `DEBUG=true`

Codex 可以创建或修改 `.env.example`，但只能写模板值，不能写真实敏感信息。

---

## 8. 关于 config.py 的约束
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

## 9. 编码范围约束
Codex 当前只允许实现第一阶段内容：

- 掼蛋引擎
- 基础规则型 AI
- RAG 规则与经验检索支持
- 4 AI 自动对局调试
- 基础测试
- 基础日志输出
- 后续可接入人类玩家的接口预留
- 环境变量模板与配置读取入口

不得实现以下内容：

- 强化学习
- 自主学习
- MCTS
- 蒙特卡洛优化
- 自博弈训练
- 高级前端
- 复杂部署系统
- 第二阶段或第三阶段功能

---

## 10. 架构约束
Codex 必须遵守以下约束：

1. 规则引擎与 AI 决策分离
2. 合法动作生成器是动作唯一入口
3. 规则引擎是动作合法性与状态更新的最终裁判
4. RAG 只能提供规则与经验知识，不能直接执行动作
5. AI 只能从合法动作集合中选择动作
6. 任何非法动作不得进入状态转移
7. 配置读取必须集中在 `config.py`
8. API 密钥和 URL 不得写死在代码中

---

## 11. 实现约束
- 使用 Python 3.11
- 优先使用标准库
- 不得猜测不存在的 API
- 不得引入无关第三方依赖
- 不得顺手重构无关代码
- 不得扩大需求范围
- 不得生成与当前文件树无关的复杂目录结构
- 不得创建 `env/` 目录来存放配置

---

## 12. 输出约束
每次 Codex 输出代码时，必须同时说明：

1. 修改了哪些文件
2. 为什么修改这些文件
3. 是否涉及 `.env.example` 或 `config.py`
4. 是否依赖环境变量
5. 覆盖了哪些当前步骤目标
6. 还未完成哪些内容
7. 是否存在与 `docs/SPEC.md` 的冲突

---

## 13. 测试约束
Codex 在实现每个步骤时，必须优先补充或更新对应测试。

没有测试支撑的功能，不应视为完成。

如果新增了配置读取逻辑，还应至少验证：
- 缺失必要环境变量时有明确错误
- 默认值行为明确
- 不依赖写死密钥