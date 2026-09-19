<div align="center">

# AI WorkDesk OS / EMILIA LAB

### 30 秒上手，把多智能体协作、QA 双重门禁与个人超级工作台装进你的 Windows 桌面。

本地优先 · 用户 > 主脑 > PM > 员工层级 · QA-1需求门禁 + QA-2质检精准返工 · 混合模型隐私路由 · 视觉工位地图 · 双链知识库 · 拟人化伴侣

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Uvicorn-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLite WAL](https://img.shields.io/badge/Database-SQLite%20(WAL)-003B57?style=flat-square&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![WebSockets](https://img.shields.io/badge/Streaming-WebSockets-orange?style=flat-square)](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)
[![Privacy First](https://img.shields.io/badge/Privacy-100%25%20Local--First-success?style=flat-square)](./#️-隐私与安全承诺)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](./LICENSE)

🌐 [English](./README.md) · **中文**　|　[📥 30 秒快速上手](#-30-秒快速上手) · [✨ 核心亮点](#-核心亮点) · [🎯 谁会想用](#-谁会想用) · [🏗️ 系统架构](#️-系统架构与运行机制) · [🆚 与传统方案对比](#-与传统方案对比) · [❓ FAQ](#-常见问题-faq)

</div>

---

## 💡 为什么需要 AI WorkDesk OS？

现在的 AI 工具大多数依然只是**单轮对话框**：
- 给你一个长长的输入框，生成内容后如果出现幻觉，要么手动纠错，要么推倒重来；
- 所谓的多智能体框架多数停留在终端命令行或庞大的 Python 代码库中，缺乏可视化的协作界面；
- 敏感数据直接发送给云端 API，缺乏本地隐私保护与精细模型分级路由。

**AI WorkDesk OS** 从底层操作系统视角出发，重新构想了人与 AI 的协同形态：
它不仅是一个拥有视觉工位地图（Office Floor）与双链笔记（Vault）的桌面工作台，更是一套具备**需求分析（QA-1）、团队委派（PM）、执行交付（Workers）、质检评分（QA-2）与依赖定向精准返工（Selective Rework）**的完整自治闭环。

---

## ✨ 核心亮点

- 🏢 **多层自治智能体体系**：严格落实 `USER > Main Brain (主脑) > Project Manager (终身制PM) > Workers (员工)` 权力梯队，主脑总揽需求，PM 长期积累项目经验与员工绩效，员工专注于专项交付。
- 🛡️ **QA-1 与 QA-2 双重门禁**：
  - **QA-1（开工前需求门禁）**：自动检测指令中的缺失项、模糊歧义、逻辑冲突与技能断层（Capability Gap），不符合开工标准决不盲目消耗 Token。
  - **QA-2（交付后质量门禁）**：多维度客观质检并评分（格式合规、事实一致、逻辑有效性）；发生缺陷时出具结构化 `FailureReport`，**仅重做受影响员工及其下游消费者**，绝不推倒全量工作。
- 📮 **Munder-Difflin 风格的交互式工位与信箱（Hive）**：
  - 俯瞰工位视角，主脑居中，员工环绕，动态展示 `idle`、`thinking`、`working`、`waiting`、`blocked`、`success` 实时状态。
  - 基于言语行为（FIPA-lite: `request` / `inform` / `propose` / `agree` / `refuse`）的异步信箱系统，工位间信封动态穿梭投递，内置 8 跳防死锁环路保护。
- 🔀 **隐私优先的混合模型路由（Hybrid Model Router）**：
  - **本地优先**：敏感任务自动路由到本地端点（Ollama / LM Studio，如 `qwen2.5:7b`、`deepseek-coder`），数据 100% 留在本机。
  - **分级分流**：轻量任务走极速模型，深度攻坚走 Claude 3.5 Sonnet / GPT-4o 等云端专家模型，内置 ChatAnywhere 免费中继支持。
  - **自动降级链**：若主选模型超时或异常，自动依次遍历回退链，全过程落地 SQLite 审计流。
- 🧠 **一键将 GitHub Skill 转化为员工**：输入任何包含 `SKILL.md` 的 GitHub 仓库 URL，系统自动递归解析元数据，一键生成带有专属设定、工具与行为准则的新员工（或合并至已有员工）。
- 📝 **双区 Obsidian 风格双链知识库（Vault）与工作区套件**：
  - 支持 `[[双链]]`、实时预览与全文检索，区分个人笔记（My Vault）与系统自动同步记忆（Main Brain Memory）。
  - 内置 Office Suite：文档编辑器（Documents）、带公式计算的表格（Sheets）、演示幻灯片（Slides）与 PDF 查看器，配合沙箱代码工坊（Code Studio）实现生产力闭环。
- 🌸 **Emilia 桌面智能体桌宠与本地视觉感知**：
  - 拟人化透明桌宠跨页面随行，配备行走、饮茶、冰魔法与睡眠等状态机。
  - **Bongo 敲击动效**：实时响应当前工作区内的真实键鼠输入。
  - **严格环回的本地视觉感知**：仅限连接 `127.0.0.1` 本地视觉模型（如 Ollama LLaVA/MiniCPM），密码框与隐私区域自动涂黑，图片仅留内存即用即焚，绝不上云。

---

## 🎯 谁会想用

| 你是 | 你的核心痛点 | AI WorkDesk OS 如何解决 |
| --- | --- | --- |
| **独立开发者 / 全栈创作者** | 一人身兼产品、架构、编码与文档，多头兼顾心力憔悴 | 主脑自动拆解需求，PM 调派 Coder/Researcher/Documenter 协同交付，自带双重质检 |
| **数据与代码隐私要求极高者** | 商业代码、客户资料不敢提交给公有云 LLM | 敏感标记任务自动走本地 Ollama / LM Studio，数据库纯单文件 SQLite 本地落盘 |
| **AI Agent 开发者与研究者** | 终端命令行多智能体交互抽象，难排查流程缺陷 | 可视化工位地图、信箱消息流、状态机时间线与结构化 QA 质检报表一目了然 |
| **个人生产力重度爱好者** | 切换于 Obsidian、Excel、VS Code 与浏览器之间，上下文频繁断裂 | 桌面一站式整合：双链笔记 + Office 套件 + 代码沙箱 + 智能伴侣 |

---

## ⚡ 30 秒快速上手

### 环境要求
- **Python 3.11+**
- **Git**
- *(可选)* [Ollama](https://ollama.com/) 或 [LM Studio](https://lmstudio.ai/)（若需 100% 离线本地模型）
- *(可选)* Node.js 18+（若需执行前端测试）

### 1. 克隆代码库
```bash
git clone https://github.com/lingjw02/ai-workdesk-local.git
cd ai-workdesk-local
```

### 2. 创建并激活虚拟环境
**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. 配置环境变量
复制示例配置文件：
```bash
cp .env.example .env
```
用编辑器打开 `.env` 填入你的偏好配置（按需启用）：
```env
# 选项 A: 使用 OpenRouter 云端模型 (可选)
OPENROUTER_API_KEY=sk-or-v1-...

# 选项 B: 本地隐私模型 (Ollama / LM Studio) (可选)
LOCAL_ENDPOINT=http://localhost:11434/v1
LOCAL_MODEL=qwen2.5:7b

# 选项 C: ChatAnywhere 免费中继 (可选)
CHATANYWHERE_API_KEY=sk-...

# 选项 D: Brave 搜索 API (若留空则自动回退至免 Key 的 Bing 本地检索)
BRAVE_API_KEY=
```

### 4. 启动服务

**方式一：Windows 桌面双击（最快）**
直接双击根目录下的 [`start_workdesk.bat`](./start_workdesk.bat)。

**方式二：命令行启动**
```bash
python main.py
# 或使用 npm
npm start
```

服务就绪后，在浏览器访问：
```
http://localhost:3787
```

---

## 🏗️ 系统架构与运行机制

```
┌────────────────────────────────────────────────────────────────────────┐
│                              用户操作终端 (Browser UI)                   │
│   • 全景仪表盘   • 对话与办公室工位地板  • 专属员工工作室 (Studio)       │
│   • 双链知识库   • 办公四件套 (Office)   • 代码沙箱与效率工具箱          │
└────────────────────────────────────┬───────────────────────────────────┘
                                     │ WebSocket 双向事件流 / REST API
┌────────────────────────────────────▼───────────────────────────────────┐
│                    FastAPI 后端服务网关 (main.py / bridge.py)           │
├────────────────────────────────────────────────────────────────────────┤
│                       Main Brain (主脑智能中枢)                         │
│   • 意图分类器 (直接应答/任务组)  • 结构化需求规约 (RequirementSpec)     │
│   • QA-1 开工前可行性门禁        • 员工能力断层感知 (Capability Gap)    │
├────────────────────────────────────────────────────────────────────────┤
│                      Lifetime PMs (终身制项目经理)                     │
│   • 目标子任务拆解与编排         • 项目知识沉淀 (Conventions/Decisions) │
│   • 员工绩效记录 (EWMA)          • 证据门禁式经验提炼 (Evidence Lessons) │
├────────────────────────────────────────────────────────────────────────┤
│                     Autonomous Workers (员工能力池)                    │
│   • 代码工程师 (Coder)           • 深度调研员 (Researcher)              │
│   • 文档撰写员 (Documenter)      • 数据分析师 (Data Analyst)            │
│   • 质量监督员 (QA Worker)       • 员工孵化专家 (Worker Creator)        │
├────────────────────────────────────────────────────────────────────────┤
│                     Tool Control (工具管控与安全沙箱)                  │
│   • 路径收敛型文件系统 (防穿越)   • 危险指令黑名单终端 (Sandbox)        │
│   • 双通道网页检索 (Brave API / Keyless Bing fallback)                 │
├────────────────────────────────────────────────────────────────────────┤
│                    Hybrid Model Router (混合模型路由)                  │
│   • 隐私级别判定 (Local First)   • 复杂度分流策略 (Instant vs Expert)   │
│   • 多级降级容灾链 (Fallbacks)   • 全链路路由与耗时审计                 │
├────────────────────────────────────────────────────────────────────────┤
│                    Local SQLite Database (纯本地持久化)                │
│   • 任务状态机 (12状态) • 关键检查点 • 向量记忆 • 审批流 • 审计日志     │
└────────────────────────────────────────────────────────────────────────┘
```

### 任务生命周期与双重门禁流转

```
用户提交需求
   │
   ▼
[Main Brain 意图理解] ──(日常问答/闲聊)──► [主脑直答，不建任务]
   │ (生产/研发任务)
   ▼
[QA-1 需求准入审核]
   ├─► 存在模糊/冲突/缺少关键输入 ──► 抛出 ClarificationNeeded，引导用户澄清
   ├─► 缺少对应技能员工 ──────────► 唤起 Worker Creator 从 GitHub 动态补足能力
   └─► 审核通过 (QA-1 PASS)
         │
         ▼
   [PM 规划任务组 (Task Group)]
         │
         ▼
   [混合模型路由 (Model Router)] ──► 隐私任务定点锁定本地，复杂任务下发云端
         │
         ▼
   [员工并行协同执行 (Workers)]
         │
         ▼
   [QA-2 交付质量综合审计]
         ├─► 质检不通过 ──► 生成 FailureReport ──► 定向调度故障员工精准返工 (Selective Rework)
         └─► 质检通过 (QA-2 PASS) ──► 归档交付件 ──► 提炼 High-Confidence 经验至 PM 知识库
```

---

## 🆚 与传统方案对比

| 对比维度 | 传统 Web 聊天机器人 | 常见命令行 Agent 框架 | AI WorkDesk OS / EMILIA LAB |
| :--- | :--- | :--- | :--- |
| **交互形态** | 单一线性瀑布式信息流 | 终端文本输出，无可视化工作区 | 完整工作台：可视化办公室工位、双链笔记、办公套件、代码沙箱 |
| **多智能体协同** | 伪协作（仅是同一上下文中更换系统提示词） | 代码层简单循环调用，容易死循环 | 独立工位信箱（FIPA-lite 协议），8 跳防死锁，PM 维护独立档案与绩效 |
| **质量控制机制** | 无质检，幻觉内容直接输出 | 出现错误盲目重试全量 Prompt | **QA-1 准入初检 + QA-2 终检验收**，只返工受损依赖链 |
| **模型调度策略** | 仅绑定单一厂商模型 | 静态环境变量硬编码 | **混合路由系统**：敏感任务强制本地化，自动回退与全链路审计 |
| **知识与记忆沉淀** | 无状态或粗暴追加对话历史 | 仅简单存入向量数据库 | 四层记忆隔离（用户/全局/项目/工作组），证据门禁式经验自学习 |
| **数据与隐私** | 对话托管在厂商云端，存在外泄风险 | 视具体实现而定 | **100% 运行在本地**，单文件 SQLite WAL 存储，零远端遥测 |

---

## 🧩 核心功能全景

### 1. 办公室工位地图与信箱（Office Floor）
- **工位可视化**：实时俯瞰主脑、PM 与各个业务员工的工位卡片，状态呼吸灯实时同步。
- **信件穿梭动效**：通过信箱给员工发号施令，信封在工位间真实平移动画投递。
- **黑板看板（Blackboard）**：PM 维护共享项目黑板，所有员工同步上下文。

### 2. 专属员工工作室（Worker Studios）
- 每个员工根据其专长拥有独立的交互式操作台：
  - **Coder Studio**：工作区文件树、代码编辑器与沙箱运行日志。
  - **Researcher Studio**：内置网页浏览器监视器与检索摘要提炼。
  - **Office Studio**：文档草稿与报表产出集中预览。

### 3. 双区知识库（Vault）
- **个人笔记区（My Vault）**：自由记录 Markdown，支持 `[[笔记名称]]` 关联与即时搜索。
- **主脑活页记忆（Main Brain Memory）**：系统自动维护 4 份核心知识文档：
  - `global-memory.md`：用户长期偏好与习惯。
  - `lessons.md`：经过多次验证沉淀的 High-Confidence 经验。
  - `todo.md`：当前进行中的任务与待审批事件。
  - `pm-knowledge.md`：各项目的规约与决策记录。

### 4. 拟人化桌面伴侣（Emilia Companion）
- 驻留在屏幕前的小巧桌宠，可随意拖拽停靠，支持休闲、魔法、茶会等丰富动作。
- **Bongo 模式**：敲击键盘时，桌宠小手同步即时敲击桌面，陪伴感拉满。
- **本地化安全视觉**：开启视觉感知后，仅通过本地 `127.0.0.1` 视觉模型理解当前页面布局，严格屏蔽密码框与私密区域。

---

## 🧪 自动化测试与质量保障

项目拥有完善的自动化测试矩阵，覆盖核心状态机、门禁路由与前端状态计算：

### 运行 Python 全量单元测试（75+ 测试全绿）
```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests
```
*包含：核心状态机测试、Phase 2-14 渐进式功能测试、混合模型路由、Vault 双链存取与本地伴侣视觉安全性校验。*

### 运行 Node.js 前端与桌宠测试（18 个用例）
```bash
node --test tests/pet-state.test.cjs tests/pet-awareness.test.cjs tests/dashboard.test.cjs
```
*包含：仪表盘指标纯函数计算、桌宠状态转移不可变性、Bongo 键盘输入捕获与环回截帧防抖测试。*

### 运行端到端流水线集成测试
先在主终端启动服务（`python main.py`），然后在第二终端运行：
```powershell
python test_pipeline.py
```
*自动完成：创建工作区 → 主脑理解意图 → PM 分解任务 → 员工并行产出 → QA-2 质检打分全流程验收。*

---

## 🛡️ 隐私与安全承诺

1. **绝对本地优先**：所有的对话、任务状态、代码交付件、笔记与审核历史均存放在本地 `data/workdesk.db` 中。
2. **密钥零泄漏**：配置信息仅存于本地 `.env`（已被 `.gitignore` 严格忽略），`.env.example` 仅保留干净的占位符。
3. **安全沙箱防逃逸**：
   - 所有的文件操作均被限制在工作区目录内部，严格拒绝 `../` 目录穿越行为。
   - 终端工具内置硬性破坏性指令黑名单（如 `rm -rf`, `format`, `del /s`, `shutdown` 等），杜绝误操作危害宿主机。
4. **桌宠视觉严格保密**：
   - 伴侣视觉捕获的图片帧仅留存在内存中用于单次推理，从不落盘。
   - 严格拒绝外部远程 IP，仅允许绑定 `127.0.0.1` 环回接口；输入框与隐私敏感组件自动遮蔽。

---

## 🗺️ 路线图 (Roadmap)

- [x] **v0.1 - v0.8**: 状态机、多员工池、终身制 PM、工具权限矩阵、QA-1/2 双门禁与混合模型路由
- [x] **v0.9 - v0.10**: 证据门禁式经验自学习系统、个人桌面实用工具与 Office Suite
- [x] **v0.11 - v0.12**: Obsidian 风格双链 Vault、GitHub Skill 一键员工生成、全景仪表盘
- [x] **v0.13 - v0.14**: Munder-Difflin 风格工位地图、言语行为信箱与动态优先级调度
- [x] **v0.18 - v0.19**: Emilia 拟人化伴侣、Bongo 敲击响应、本地环回视觉安全感知、Liquid 流体主题
- [ ] **v0.20+ (规划中)**:
  - [ ] 接入本地语音交互与情绪合成（TTS / STT）
  - [ ] 基于 Tauri 的轻量级原生 Windows / macOS 桌面封装
  - [ ] 多机器局域网节点分布式工位组网

---

## ❓ 常见问题 (FAQ)

<details>
<summary><b>Q: 我没有付费的 OpenRouter 或 OpenAI API Key，能正常使用吗？</b></summary>
<br/>
<b>完全可以！</b>
AI WorkDesk 深度支持本地离线模型。你只需安装并启动 Ollama，在 <code>.env</code> 中设置 <code>LOCAL_ENDPOINT=http://localhost:11434/v1</code> 和 <code>LOCAL_MODEL=qwen2.5:7b</code>，所有任务调度与对话均可在本地全免费运行。此外，系统也原生兼容 ChatAnywhere 提供的免费中继 API。
</details>

<details>
<summary><b>Q: 什么是 QA-1 与 QA-2 双重门禁？它如何帮我省 Token？</b></summary>
<br/>
传统的 Agent 一旦收到不清晰的指令就会胡乱猜测并盲目生成，消耗大量 Token 后产出废品。<br/>
- <b>QA-1</b> 是前置门禁：在调度员工前审查需求是否自相矛盾、是否存在信息缺失。如果缺失则暂停并引导你补充，防止错误指令进入下游。<br/>
- <b>QA-2</b> 是后置验收：对交付的代码或报告做事实性与格式合规打分。如果某部分不合格，系统通过依赖分析<b>仅通知出问题的员工重做</b>，不用推倒重来，大幅节省 Token 与等待时间。
</details>

<details>
<summary><b>Q: 伴侣桌宠的视觉感知会不会偷看我的屏幕？</b></summary>
<br/>
<b>绝对不会。</b>
1. 伴侣视觉默认处于<b>关闭</b>状态，必须用户手动在设置中开启；<br/>
2. 视觉捕获仅捕获当前应用窗口内的操作区域，屏幕其他软件完全不可见；<br/>
3. 密码输入框、私密字段在截图渲染前会被 DOM 过滤器<b>强制遮蔽</b>；<br/>
4. 推理仅向本地 <code>127.0.0.1</code> 端口发送请求，图片帧不保存到硬盘，推理结束立即销毁。
</details>

<details>
<summary><b>Q: 如何将 GitHub 上的第三方 Agent Skill 转化为我的员工？</b></summary>
<br/>
在侧边栏进入 <b>Workers</b> 页面，点击 <b>Design New Worker</b>，粘贴任意包含 <code>SKILL.md</code> 的 GitHub 仓库链接。系统会自动下载并解析该 Skill 的名称、能力描述、行为守则与权限，你可以一键创建全新员工，或将能力无缝合并到既有员工中。
</details>

---

## 🤝 参与贡献

欢迎提交 Issue 与 Pull Request 共同完善 AI WorkDesk OS！
- 发现 Bug 或有新功能想法？欢迎提交 [GitHub Issues](https://github.com/lingjw02/ai-workdesk-local/issues)。
- 想贡献好玩的员工 Skill？欢迎在社区分享你的 `SKILL.md` 预设。

---

## 📄 开源协议

本项目采用 [MIT License](./LICENSE) 开源许可。
<br/>
Copyright (c) 2026 AI WorkDesk Authors.
