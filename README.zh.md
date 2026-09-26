<div align="center">

# AI WorkDesk OS / EMILIA LAB

### 一个运行在 Windows 上的个人 AI 操作系统。一个 Main Brain（主脑）理解你的目标、规划并监督工作，创建或选择持久化的 AI 员工，协调项目团队，通过 QA 验证结果，从历史中学习，并以用户批准的自主权驱动电脑工具。

**AI 模型不是产品，围绕模型构建的 WorkDesk 编排系统才是产品。**

本地优先 · USER > Main Brain > PM > Worker 层级 · QA-1 需求门 + QA-2 输出门与选择性返工 · 基于技能的路由（SBR）· 四层记忆隔离 · 四级权限系统 · 本地/云端混合模型路由 · 可视化办公楼层 · Obsidian 风格 Vault · 开场动画与桌面伙伴

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI%20%7C%20Uvicorn-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![SQLite WAL](https://img.shields.io/badge/Database-SQLite%20(WAL)-003B57?style=flat-square&logo=sqlite&logoColor=white)](https://www.sqlite.org/)
[![WebSockets](https://img.shields.io/badge/Streaming-WebSockets-orange?style=flat-square)](https://developer.mozilla.org/en-US/docs/Web/API/WebSockets_API)
[![Privacy First](https://img.shields.io/badge/Privacy-100%25%20Local--First-success?style=flat-square)](#-隐私与安全不变量)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](./LICENSE)

🌐 [English](./README.md) · **中文**　|　[📥 快速开始](#-30-秒快速开始) · [✨ 亮点](#-亮点) · [🏗️ 愿景架构](#️-愿景架构) · [🖥️ 当前版本](#-当前版本-emilia-lab-studio) · [🗺️ 路线图](#-路线图)

</div>

---

## 💡 一句话概念

一个基于 Windows 的个人 AI 操作系统：一个 **Main Brain（主脑）** 理解你的目标、规划并监督工作，创建或选择拥有专业技能的持久化 **AI 员工（Worker）**，在 **项目管理者（PM）** 的协调下组建项目团队，通过 **QA** 验证结果，从历史经验中学习，并在 **用户批准的自主权** 下控制电脑工具。

**用户告诉系统目标，而不是每一步怎么做。主脑负责想办法。** 这正是它区别于普通 agent 框架、成为 AI 操作系统的地方。

---

## ✨ 亮点

- 🧠 **主脑编排器（Main Brain）**：理解自然语言、执行需求 QA、规划执行、选择或创建 worker、路由模型、管理权限、持有全局记忆、监督 PM，并对每个决策拥有最终权威。
- 🏢 **权威层级**：`用户 > 主脑 > 项目经理 > Worker`。任何超出层级授权范围的决策都按此顺序逐级上报。
- 🛡️ **双 QA 验证门**：
  - **QA-1（执行前）**：在花费任何 token 之前，检测歧义、矛盾、信息缺失和能力缺口。
  - **QA-2（执行后）**：审计准确性、真实性、完整性、需求符合度、格式、逻辑与来源有效性。失败时生成结构化 FailureReport 并触发 **选择性返工** - 只重做失败的 worker 及其下游依赖，绝不重启整个项目。
- 📦 **持久 AI 员工**：Worker 与 PM 不是一次性 agent。它们跨会话、跨项目保留身份、个性、技能、工具、权限、记忆规则、经验与绩效统计。
- 🔀 **基于技能的路由（SBR）**：系统把工作路由到正确的技能、worker 和模型。worker 从不关心背后是本地还是云端模型；路由层根据复杂度、隐私、成本、速度、上下文大小、能力与用户偏好决定。
- 🧩 **从 GitHub 技能创建 Worker**：粘贴任意包含 `SKILL.md` 的 GitHub 仓库 URL。系统递归扫描子文件夹、读取技能 frontmatter，自动设计 worker - 无需手动命名。相似 worker 可合并，创建后仍可编辑。
- 🔒 **四级权限系统**：`自动（安全常规操作）→ 通知（执行后告知）→ 询问（需用户批准）→ 显式（高影响操作需直接确认）`。拥有工具绝不等于拥有无限使用权。
- 🧠 **四层记忆隔离**：全局记忆、项目记忆、Worker 记忆、任务组记忆严格分离。跨项目访问永不自动发生，必须由主脑显式授权。
- 📝 **Obsidian 风格 Vault**：你的个人笔记与主脑的活记忆（global-memory、lessons、todo、pm-knowledge）并排存放，支持 `[[wiki links]]`、全文搜索，以及内建的"告知主脑存入内容"聊天框。
- 🖥️ **可视化办公与工作图**：每个聊天会话都携带可调宽度的 "THIS CHAT SESSION" 面板（TASKS / OFFICE / APPROVALS / RESULT / PROJECT 五个标签页），主聊天区还有 Office Workflow View。
- 🎬 **开场体验**：主脑标志 SVG 描边动画启动序列（状态逐条点亮 + 进度线），尊重 `prefers-reduced-motion`，可一键跳过。
- 🌸 **Emilia 桌面伙伴**：浮动角色伙伴，带状态机、打字反应和严格回环本地视觉。

---

## 🏗️ 愿景架构

### 终极架构

```
                         ┌───────────┐
                         │   USER    │
                         └─────┬─────┘
                               ▼
                     ╔══════════════════╗
                     ║    MAIN BRAIN    ║
                     ║  理解  思考  规划  ║
                     ║  委派  记忆       ║
                     ║  验证  保护       ║
                     ╚════════╤═════════╝
                              │
         ┌────────────────────┼────────────────────┐
         ▼                    ▼                    ▼
     知识库                PROJECTS             WORKERS
                              │                    │
                              ▼                    ▼
                            PMs                 SKILLS
                              │                    │
                              └─────────┬──────────┘
                                        ▼
                                   TASK GROUPS
                                        │
                               ┌────────┼────────┐
                               ▼        ▼        ▼
                            Worker   Worker   Worker
                               │        │        │
                               └────────┼────────┘
                                        ▼
                                       QA
                                        │
                                 ┌──────┴──────┐
                                 ▼             ▼
                               FAIL           PASS
                                 │             │
                                 ▼             ▼
                                PM           FINAL
                                 │             │
                                 ▼             ▼
                              REWORK          USER
```

### Main Brain（主脑）

全局智能与权威。它不把所有信息塞进一个上下文，而是通过访问正确的记忆、知识与注册表系统来"知道"整个 WorkDesk。

| 职责 | 目的 |
| :--- | :--- |
| 需求理解 | 把自然语言转化为结构化需求 |
| 需求 QA | 检测歧义、矛盾与缺失信息 |
| 提示协助 | 帮助用户细化模糊请求 |
| Worker 选择 | 找到合适的现有 worker |
| Worker 创建 | 能力缺失时请求/创建新技能 |
| 任务规划 | 决定工作如何执行 |
| 模型路由 | 按任务决定本地或云端模型/API |
| 权限管理 | 决定何时需要用户批准 |
| 全局记忆 | 记住长期信息 |
| 知识库 | 访问 WorkDesk 与项目知识 |
| 项目监督 | 监控 PM 与重大决策 |
| 最终权威 | 主脑高于 PM 与 Worker |

### Project Manager（项目经理）

持久化的项目员工，而非一次性 agent。项目创建时指派 PM，PM 终身依附于该项目，成为项目的机构记忆：项目知识、项目决策、历史任务、worker 绩效、失败案例、成功工作流、经验教训、项目约定。PM 永不自动读取无关项目的记忆。

### Workers（AI 员工）

持久化 AI 员工。一个 Worker 本质上是：**身份 + 个性 + 技能集 + 工具 + 权限 + 记忆规则 + 经验 + 绩效**。

- **技能**：主技能、副技能、专长
- **工具**：浏览器、终端、文件系统、代码工作室、办公套件、媒体等
- **权限**：允许的应用、允许的文件夹、读/写/删权限、审批要求
- **记忆**：组记忆、被授权的项目记忆、worker 经验
- **统计**：触发次数、完成任务数、QA 通过率、失败率、平均执行时长
- **状态**：空闲 · 工作中 · 等待 · 需要主脑 · 需要用户 · 离线

### Worker 创建系统

五条进入 worker 注册表的路径：

1. GitHub 技能仓库（递归扫描子文件夹）
2. Skill Creator Worker（设计其他 worker 的元 worker）
3. 用户手动创建
4. PM 请求新 worker
5. **能力缺口检测**：主脑发现"没有现有 worker 能胜任此任务"，检查现有 worker 是否可升级，然后选择升级或新建。

---

## 🛡️ 双 QA 系统

### QA-1：需求 QA（工作开始前）

验证主脑是否正确理解用户：

- 有任何歧义吗？· 有矛盾吗？· 需求足够完整吗？· 请求的输出定义清晰吗？· 任务可行吗？

示例：用户说"给我的项目做个演示文稿"。主脑理解了主题，但页数和语言未知。QA-1 FAIL，触发澄清请求，主脑询问用户。

### QA-2：输出 QA（执行结束后）

验证：准确性 · 真实性 · 正确性 · 完整性 · 需求符合度 · 输出偏好 · 格式 · 逻辑 · 技术功能 · 来源有效性。

```
QA
 │
 ▼
失败报告
 │
 ▼
PM 识别责任 worker
 │
 ▼
只重做失败的部分
 │
 ▼
再次 QA
```

这避免了整个项目被无谓地推倒重来。

---

## 🧠 记忆架构

```
                         MEMORY
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
    全局记忆            项目记忆           Worker 记忆
         │                   │                   └── 身份
         │                   │                       经验
         │                   │                       绩效
         │                   └── PM / 项目知识
         └── 用户偏好
             WorkDesk 设置
             全局知识
             长期决策
```

**组记忆** 存在于项目/任务组之下，用于短期协作。

| 角色 | 可访问范围 |
| :--- | :--- |
| 主脑 | 全局 + 被授权的项目/组信息 |
| PM | 自己的项目 + 当前组 |
| Worker | 当前组 + 自己的档案/经验 |
| 跨项目 | 永不自动；由主脑授予权限 |

---

## 📚 学习系统

Worker 与 PM 从历史中进步 - 但不存在不受控的自我改写。

```
任务 → 结果 → QA → 经验 → 课程候选 → 证据 / 置信度 → 存储课程
```

示例：Excel worker 生成了错误公式。QA 确认。课程候选："公式验证应在格式化之后进行。" 证据：3 个相似案例。置信度：高。AI 从证据中学习，而不是盲目信任自己先前的结论。

---

## 🗂️ 任务组（Task Group）

任务组是临时工作团队：PM + Workers + 共享需求 + 共享文件 + 共享产物 + 组记忆 + 通信 + 任务状态。

- Worker 可在组内直接通信。
- 重要决策逐级上报：**Worker → PM → 主脑 → 用户**。
- 等待用户的 worker 不会冻结整个组。任务引擎支持**异步执行**。

---

## 🔧 工具与权限

### 工具生态

| 现在 | 未来 |
| :--- | :--- |
| 文件系统、终端、网页搜索、代码工作室、办公套件（PDF）、媒体、Vault、远程设备 | 邮件、Discord、Slack、GitHub、数据库、设计工具、其他 Windows 应用 |

### 四级权限系统

| 级别 | 行为 |
| :--- | :--- |
| 自动 | 安全常规操作 |
| 通知 | 执行后告知用户 |
| 询问 | 用户必须批准 |
| 显式 | 高影响操作需直接确认 |

示例：读取项目文件 → 自动。创建新项目文件 → 自动/通知。修改重要项目配置 → 询问。安装软件 / 删除重要文件 / 外部操作 → 显式批准。

---

## 🔀 模型路由与 SBR

```
                 Main Brain
                      │
                 Model Router
         ┌────────────┼────────────┐
         ▼            ▼            ▼
      本地 AI      云端 AI      其他 API
```

路由器考虑：任务复杂度、隐私、成本、速度、上下文大小、模型能力、工具需求与用户偏好。**基于技能的路由（SBR）** 让整个系统把每个请求路由到正确的技能 → 正确的 worker → 正确的模型，而 worker 定义本身保持模型无关。

示例：私有文件分析 → 本地。复杂推理 → 云端。简单分类 → 本地。专用 API 任务 → 指定 API。

---

## 👁️ 可视化

两种视图让 AI 的工作过程可见：

1. **工作图（Work Graph）** - 每个任务从 MB → PM → Workers → QA → DONE 的流转。
2. **虚拟办公室 / Office Workflow View** - 数字职场，worker 状态：空闲 · 工作中 · 思考/规划 · 等待 · 与另一 worker 对话 · 询问 PM · 等待用户 · 完成 · 出错。

两者都**存在于每个聊天会话内部**，而不是独立页面 - 因为每个聊天有自己的 worker 与流程。

---

## 🛡️ 可靠性：四大安全系统

1. **审计日志** - 谁做的决定、哪个 worker 行动、用了哪个工具、改了什么文件、主脑为何这样决定、QA 拒绝了什么、返工改了什么。记录决策/事件元数据，而非隐藏思维链。
2. **检查点** - 重大操作前：当前状态 → 检查点 → worker 行动 → 若造成破坏可回滚。
3. **取消** - 用户随时可以说"Stop"：主脑停止任务组、取消 worker、安全终止活动工具、保留当前状态。没有良好紧急刹车的自主 AI 是一场事故。
4. **恢复** - 任务状态、检查点、记忆与产物全部持久化，可承受应用重启、电脑重启、API 失败、worker 失败与网络失败。

---

## 🖥️ 当前版本：EMILIA LAB Studio

EMILIA LAB 是 AI WorkDesk OS 当前面向用户的身份：一个运行在 Windows 上、服务地址为 `http://localhost:3787` 的安静个人 AI 工作室。

### 设计系统

- **配色**：石墨画布、抬升的炭色表面、单一淡冷蓝主色（`#5B8DEF`）、高对比近白文本
- **字体**：本地可用的 Segoe UI（贴近 Windows 操作习惯）；等宽字体专用于代码与数值
- **形状**：控件 8px 圆角、大面板 12px、装饰克制、边框定义表面
- **动效**：液态而克制；尊重 `prefers-reduced-motion`（开场动画降级为纯淡入）
- **身份**：EMILIA LAB 字标、导航底部与首页欢迎区的 Emilia 角色画像、主脑开场动画

### 页面（侧边栏）

| 分组 | 视图 |
| :--- | :--- |
| HOME | 首页仪表盘、新建聊天、项目、任务 |
| Recent chats | 会话历史 |
| Your team | Workers、Worker 注册表、Worker 设计（GitHub 技能导入）、项目经理、团队记忆（Vault） |
| Workspace | 办公套件（PDF 工作室）、代码工作室、媒体室、远程设备 |
| Utilities | 计时器 · 闹钟 · 秒表、计算器 |
| System | 审计日志、设置 |

### 本版本功能状态

| 功能 | 状态 |
| :--- | :--- |
| 主脑 agent 式聊天 + Office Workflow View | ✅ |
| THIS CHAT SESSION 面板（TASKS / OFFICE / APPROVALS / RESULT / PROJECT），可调宽 | ✅ |
| QA-1 / QA-2 门 + 选择性返工 | ✅ |
| Worker 注册表 + GitHub 技能 worker 设计（递归扫描文件夹） | ✅ |
| 带项目记忆的持久 PM | ✅ |
| Vault 笔记（个人 + 主脑自动记忆、`[[wikilinks]]`、主脑聊天框） | ✅ |
| 办公套件：PDF 阅读器、页内文本编辑、保存编辑、导出 PDF、全屏 | ✅ |
| 代码工作室（编辑器 + 文件树 + 运行） | ✅ |
| 媒体室：预览舞台 + 播放控制、lightbox、大小徽章、字幕 | ✅ |
| 远程设备：本机信息、注册、配对 token、设备列表、会话命令 | ✅ |
| 计时器 / 闹钟 / 秒表、计算器 | ✅ |
| 混合模型路由（OpenRouter、ChatAnywhere、本地端点） | ✅ |
| 审计日志、检查点、取消、恢复 | ✅ |
| 开场动画（可跳过、尊重减少动效） | ✅ |
| Emilia 桌面伙伴（状态机、打字反应、回环视觉） | ✅ |
| 聊天内本地磁盘浏览（C: / D: / 项目文件夹） | ✅ |

### 技术栈

- **后端**：Python 3.11+ · FastAPI · Uvicorn · WebSockets · SQLite（WAL）
- **前端**：原生 HTML / CSS / JS（无框架）、SVG 图标系统、确定性组件
- **第三方库**：pdf.js + pdf-lib（PDF 渲染/编辑）、html2canvas
- **模型**：OpenRouter（云端专家）· ChatAnywhere（免费中转）· Ollama / LM Studio（本地、隐私优先）

---

## ⚡ 30 秒快速开始

### 前置要求

- **Python 3.11+**
- **Git**
- *（可选）* [Ollama](https://ollama.com/) 或 [LM Studio](https://lmstudio.ai/) 用于离线推理
- *（可选）* Node.js 18+ 用于运行前端测试

### 1. 克隆仓库

```bash
git clone https://github.com/lingjw02/ai-workdesk-local.git
cd ai-workdesk-local
```

### 2. 创建虚拟环境

**Windows（PowerShell）：**

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
```

**macOS / Linux：**

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 启用你想要的提供商：

```env
# 云端专家模型（可选）
OPENROUTER_API_KEY=sk-or-v1-...

# 本地隐私模型（可选）
LOCAL_ENDPOINT=http://localhost:11434/v1
LOCAL_MODEL=qwen2.5:7b

# 免费中转（可选）
CHATANYWHERE_API_KEY=sk-...

# 网页搜索 API（可选 - 留空默认使用无密钥的 Bing 搜索）
BRAVE_API_KEY=
```

### 4. 启动服务器

**方式 A - Windows 双击启动（最快）：**
双击项目根目录的 [`start_workdesk.bat`](./start_workdesk.bat)。

**方式 B - 终端：**

```bash
python main.py
# 或使用 npm
npm start
```

浏览器打开：

```
http://localhost:3787
```

---

## 🏗️ 实现架构

```
WINDOWS DESKTOP
        │
        ▼
┌─────────────────────────────┐
│         UI LAYER            │  原生 HTML/CSS/JS、SVG 图标、studio shell
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│       ORCHESTRATION         │  主脑 · 任务管理器 · PM 管理器
│                             │  Worker 管理器 · QA 管理器 · 权限管理器
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│       AGENT RUNTIME         │  PMs · Workers · Skills（SBR）
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│       MEMORY / DATA         │  全局 · 项目 · 组 · 经验
│                             │  知识库 · 审计日志 · SQLite（WAL）
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│          TOOLS              │  文件系统 · 终端 · 浏览器 · 代码工作室
│                             │  PDF 套件 · 媒体 · 远程设备
└──────────────┬──────────────┘
               │
┌──────────────▼──────────────┐
│        MODEL ROUTER         │  本地模型 · 云端 API · 用户 API 密钥
└─────────────────────────────┘
```

### 任务生命周期与双 QA 执行流

```
用户提交请求
   │
   ▼
[主脑意图分类] ──(普通聊天/问答)──► [直接回答，不创建任务]
   │（可执行任务）
   ▼
[QA-1 需求录入门]
   ├─► 模糊 / 矛盾 / 信息缺失 ──► 向用户澄清
   ├─► Worker 池缺少能力 ────────► Worker Creator（GitHub 技能）
   └─► 已验证且完整（QA-1 通过）
         │
         ▼
   [PM 规划任务组（拆解与组队）]
         │
         ▼
   [模型路由 + SBR] ──► 敏感 → 本地 · 深度推理 → 云端
         │
         ▼
   [自主 Workers 并行执行（异步）]
         │
         ▼
   [QA-2 输出验证门]
         ├─► 失败 ──► 失败报告 ──► 选择性返工（只重做失败节点）
         └─► 通过 ──► 交付输出 ──► 提升有证据门控的经验课程
```

---

## 🧪 测试与质量保障

### 运行 Python 单元测试

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests
```

覆盖核心状态机、功能套件、混合路由回退、Vault API 与回环伙伴视觉安全。

### 运行前端与伙伴测试（Node.js）

```bash
node --test tests/pet-state.test.cjs tests/pet-awareness.test.cjs tests/dashboard.test.cjs
```

### 运行端到端流水线测试

服务器运行中（`python main.py`）时，另开终端执行：

```powershell
python test_pipeline.py
```

验证工作区创建、意图解析、子任务分发、worker 输出与 QA-2 审计评分。

---

## 🛡️ 隐私与安全不变量

1. **本地优先数据存储**：所有会话、任务状态、产物、Vault 笔记与审计均存于本地 `data/workdesk.db`。零遥测离开你的机器。
2. **密钥保护**：凭据严格存放于 `.env`（Git 已忽略）。`.env.example` 提供无活动密钥的脱敏模板。
3. **沙箱防护**：文件系统操作被路径限制在工作区内；终端工具强制不可变安全黑名单，拦截危险命令。
4. **伙伴视觉隔离**：视觉帧仅存于内存用于推理，拒绝非回环来源，遮罩密码字段，永不写入磁盘。
5. **权限门**：每个 worker 动作都经过四级权限系统；高影响操作始终需要用户显式确认。

---

## 🗺️ 路线图

构建遵循分阶段计划：规格 → 核心引擎 → 主脑 → worker 生态 → PM 生命周期 → 工具控制 → QA/返工 → Windows UI → 模型路由 → 学习系统 → AI OS 扩展。

- [x] **Phase 0**：系统规格（MB / PM / Worker / QA / Task / Memory / Permission / Tool 协议；生命周期；错误处理）
- [x] **Phase 1**：核心引擎（任务引擎、worker 注册表、PM 注册表、agent 运行时、消息总线、状态机、记忆管理器）
- [x] **Phase 2**：主脑（需求理解、QA-1、澄清、worker 选择、任务分类、任务组、权限、全局记忆）
- [x] **Phase 3**：Worker 生态（研究、编码、数据、文档、文件、QA worker；注册表、档案、安装、统计）
- [x] **Phase 4**：PM 生命周期系统（持久 PM 身份、项目记忆、组记忆、历史、worker 绩效、课程）
- [x] **Phase 5**：工具控制（文件系统、终端、浏览器、代码工作室、办公套件、媒体）
- [x] **Phase 6**：QA/返工引擎（QA-1、QA-2、结构化失败报告、选择性返工、重试上限、升级）
- [x] **Phase 7**：EMILIA LAB Windows WorkDesk UI（聊天、项目、任务组、worker、PM、vault、权限、审计、设置；工作图；Office Workflow View；开场动画）
- [x] **Phase 8**：模型路由（本地模型、云端 API、多提供商、任务路由、隐私路由、回退）
- [x] **Phase 9**：学习系统（证据门控课程；PM / worker / 主脑在严格记忆边界内学习）
- [ ] **Phase 10（规划中）**：AI OS 扩展 - Windows 应用控制、邮件/日历、GitHub、数据库、自动化、定时工作、后台 agent、通知、长期项目、局域网分布式 worker、Tauri 桌面壳、本地语音交互

---

## ❓ 常见问题

<details>
<summary><b>没有付费 API 密钥可以使用吗？</b></summary>
<br/>
<b>完全可以！</b>
安装并启动 Ollama，在 <code>.env</code> 中配置 <code>LOCAL_ENDPOINT=http://localhost:11434/v1</code> 和 <code>LOCAL_MODEL=qwen2.5:7b</code>，所有编排与聊天即可完全离线运行。也可使用免费的 ChatAnywhere 中转。
</details>

<details>
<summary><b>QA-1 与 QA-2 如何节省 token？</b></summary>
<br/>
传统 agent 收到模糊指令就直接开干，把 token 浪费在错误输出上。<br/>
- <b>QA-1</b> 是录入门：在派发 worker 前检查矛盾与缺失信息，先向用户澄清。<br/>
- <b>QA-2</b> 验证最终输出。若某个组件失败，引擎只重做失败的那个 worker，而非整个项目。
</details>

<details>
<summary><b>桌面伙伴会监控其他应用吗？</b></summary>
<br/>
<b>不会。</b>
视觉感知默认关闭，需显式开启。开启时仅捕获 EMILIA LAB 窗口内的可见内容，自动遮罩密码字段，且只与本地 <code>127.0.0.1</code> 模型通信。
</details>

<details>
<summary><b>如何把 GitHub 技能仓库变成活跃 worker？</b></summary>
<br/>
打开 <b>Workers → Design New Worker</b>，粘贴任意 GitHub 仓库 URL。系统递归扫描其子文件夹中的 <code>SKILL.md</code>，解析 frontmatter 与能力，自动设计 worker。可安装为新 worker 或合并进现有 worker。无需手动命名。
</details>

<details>
<summary><b>为什么聊天不再是单一对话框？</b></summary>
<br/>
因为每段会话都有自己的 worker、流程、审批与产物。聊天区因此携带 <b>Office Workflow View</b>，可调宽的 <b>THIS CHAT SESSION</b> 面板只显示该会话的 TASKS / OFFICE / APPROVALS / RESULT / PROJECT。主脑像普通 AI agent 一样回复 - 叙述它的想法与做法，而不仅仅是汇报状态。
</details>

---

## 🤝 参与贡献

欢迎提交贡献、Issue 与功能请求！

- 发现 bug 或有功能建议？请在 [Issue](https://github.com/lingjw02/ai-workdesk-local/issues) 中提出。
- 想分享 agent 技能？把你的 `SKILL.md` 配置分享给社区。

---

## 📄 许可证

本项目基于 [MIT License](./LICENSE) 授权。
<br/>
Copyright (c) 2026 AI WorkDesk Authors.
