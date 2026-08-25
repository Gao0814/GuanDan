# 下一任务提示词

## Step L5-A4f6：Botzone GuanDan 建桌 UI 选择器契约发现

L5-A4f5 唯一判定：

```text
botzone_codex_click_fenced_rule_pilot_invalid
```

白名单内的游戏选择确认已点击，但页面没有进入预期建桌表单，仍停留在主页。按契约未盲目重试；connector、pilot 目录、网页桌、DeepSeek、runmatch 和仓库改动均为 0。seed `34001` 永久禁用。

### 目标

本步骤只发现并锁定 Botzone 当前网页中从主页进入 GuanDan 建桌表单的真实 UI 契约。不得启动 connector、不得点击最终“开始游戏”、不得创建对局、不得消耗新的 live seed。

需要明确：

- “创建游戏桌”打开后的可见 modal/dialog 作用域；
- GuanDan 选项的唯一语义 locator；
- 选中后的可读状态；
- 该 modal 内唯一“确认”按钮；
- 点击确认后的成功状态信号；
- “载入上次配置”和最终“开始游戏”所在表单作用域。

### 权限与隐私

- 项目计划内操作使用常驻默认授权，不再询问项目授权。
- 本步骤不需要仓库外写入、connector、Botzone local-AI GET 或 DeepSeek 网络。
- 不读取或输出连接 URL、密钥、Cookie、账号、Bot ID/名称、match、牌或其他敏感值。
- 截图与 DOM 只在当前任务内存中检查，不写入仓库或外部审计。
- 若任一点击被确认会直接创建外部桌而非仅打开/切换配置表单，必须在该点击前按浏览器平台规则做即时确认；否则不提前询问。

### 浏览器规则

1. 使用 Browser 扩展 claim 当前已登录的 `https://www.botzone.org.cn/` 标签页；不得使用桌面坐标猜测或其他浏览器。
2. 每一步先取得当前 screenshot 与 DOM snapshot，确认页面状态后再操作。
3. 所有 locator 必须位于当前可见 modal/dialog 或明确的建桌表单作用域内；禁止全页面按第一个同名文本点击。
4. 禁止点击关闭、取消、返回、退出、结束、终止、离开、解散、删除、刷新、浏览器后退、页面 `×` 或最终“开始游戏”。
5. 任一步无唯一 locator、元素不可见/不可用、选中状态不可证明或状态转换不符时立即停止；不得盲目重试或改用坐标。

### 执行顺序

1. 只读确认无残留 connector，`34001` 没有 state/audit/root，工作区没有新的代码/测试改动。
2. claim Botzone 标签页并读取主页 DOM；确认存在唯一可见“创建游戏桌”。
3. 点击“创建游戏桌”一次，随后读取 screenshot 和 DOM；确认游戏选择 modal/dialog 可见。
4. 在该 modal 内查找 GuanDan 选项。读取其控件类型、可见文本和当前 selected/checked 状态；不得读取其他 Bot 或账号信息。
5. 若未选中，使用该 modal 内的语义 locator 点击 GuanDan 一次。随后重新读取 DOM，并以 checked/selected/active 等可读状态证明 GuanDan 已选中。仅文字存在不算选中证据。
6. 在同一 modal 内定位唯一可见且启用的“确认”按钮。记录非敏感 locator 结构和按钮计数；确认作用域外同名按钮不会被命中。
7. 点击该 modal 的“确认”一次，并用状态等待而不是固定盲等：等待 modal 消失，或等待建桌表单中的“载入上次配置”/“开始游戏”出现。
8. 读取新的 screenshot 和 DOM：
   - 若已出现建桌表单，确认 `载入上次配置` 与最终 `开始游戏` 均存在且位于同一表单作用域；到此立即停止，禁止继续点击；
   - 若仍在主页，读取当前可见 modal、alert/dialog、错误提示和 console error 的低敏感摘要，立即停止，不重试；
   - 若页面进入其他状态，只输出非敏感状态类别并停止。
9. 将当前标签页标记 handoff，保留给下一任务；不得关闭页面或提交桌。

### 输出契约

只输出以下非敏感 UI 契约：

- page state 序列；
- 每一步 modal/form 的可见性；
- GuanDan locator 类型与 selected proof；
- modal-scoped confirm locator 与匹配数量；
- 点击确认后的 readiness signal；
- `载入上次配置` 和 `开始游戏` 的表单作用域与匹配数量；
- browser write action count；
- connector/GET/DeepSeek/runmatch/table-submit count 均为 0。

不得输出完整 DOM、截图、Bot ID/名称、账号、URL 参数或隐藏字段。

### 判定

成功进入建桌表单且未点击最终提交：

```text
botzone_guandan_table_ui_selector_contract_verified
```

未进入表单或契约不唯一：

```text
botzone_guandan_table_ui_selector_contract_invalid
```

invalid 时不重试当前交互序列；下一步必须基于已观察的具体状态重新规划，不得直接启动 connector。

### 后续边界

只有 UI selector contract verified 后，才能使用全新 seed/root 恢复 Codex 自动 RuleBased pilot。该步骤不形成协议、策略或胜率结论。
