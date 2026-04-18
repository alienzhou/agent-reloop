# Meta Skills 设计文档

> 更新时间：2026-04-19  
> 来源：`.discuss/2026-04-11/reloop-framework-architecture/`

---

## 一、概述

Meta Skills 是框架内置的三个生成器，在**初始化阶段**使用，帮助用户定义任务目标和评估标准。

### 定位

| Meta Skill | 角色 | 输出 | 定位 |
|------------|------|------|------|
| **INTENT Builder** | 澄清任务目标 | `INTENT.md` | 轻量级，快速完成 |
| **Evaluator Builder** | 交互式定义评估标准 | Skill 文件 + 脚本 | 主要投入精力 |
| **Mocker** | 从定义推断输出，模拟执行 | Mock executor artifacts | 验证评估器 |

### 核心原则

- **INTENT** = 目标是什么？
- **Evaluator** = 如何判断达成目标？
- **Mock** = "达成"长什么样？

### 调用规则

- 建议顺序：INTENT → Evaluator → Mock
- **不是强制流程**，可随时重新进入任意 Meta Skill
- "锁定"是用户行为，系统不强制

---

## 二、INTENT Builder

### 设计目标

帮助用户明确任务目标，生成清晰的 `INTENT.md` 文件。

### 输入输出

| 输入 | 输出 |
|------|------|
| 用户口头描述 | `task/INTENT.md` |

### INTENT 文件规范

INTENT 只包含：
- 任务描述
- 粗略的预期输出

**不包含**：
- 验收标准（Evaluator 的职责）
- 实现细节

### 交互流程

```
用户: 我想写一个 Python 脚本统计文件词频
↓
INTENT Builder Agent 提问:
  - 输入文件格式是什么？
  - 输出格式有要求吗？
  - 是否需要处理中文？
↓
用户回答
↓
生成 INTENT.md
```

### Skill Prompt 模板

```markdown
# INTENT Builder

你是一个任务澄清助手。你的目标是帮助用户明确任务目标，生成清晰的 INTENT 文件。

## 工作流程

1. **初步理解**：让用户用一句话描述他们想要什么
2. **澄清问题**：针对模糊点提出 3-5 个问题
3. **确认理解**：复述任务目标，确认理解正确
4. **生成 INTENT**：输出结构化的 INTENT.md

## INTENT 格式

```markdown
# Task Intent

## 目标
[一句话描述最终目标]

## 背景
[任务的上下文和动机]

## 输入
[输入内容的描述]

## 输出
[期望输出的描述]

## 约束
[任何限制或边界条件]
```

## 规则

- 保持轻量，不要过度设计
- 不讨论如何实现，只关注"是什么"
- 不定义验收标准（那是 Evaluator 的工作）
- 如果用户要求细节，引导他们去使用 Evaluator Builder
```

---

## 三、Evaluator Builder

### 设计目标

交互式帮助用户定义评估标准，生成 Evaluator Skill 和配套脚本。

### 输入输出

| 输入 | 输出 |
|------|------|
| INTENT.md + 用户交互 | `task/EVAL_SKILL.md` + 验证脚本 |

### 三层评估框架

| Layer | 含义 | 检测方式 |
|-------|------|----------|
| L0 | 前置条件 / 安全检查 | 脚本 |
| L1 | 机械性验证（确定性） | 脚本 |
| L2 | 质量性验证（语义） | LLM |

**短路机制**：L0 → L1 → L2，任一层失败则停止

### 交互流程

```
读取 INTENT.md
↓
Evaluator Builder Agent 提问:
  - 什么情况下认为任务失败？（L0）
  - 输出必须满足什么格式？（L1）
  - 输出质量如何评判？（L2）
↓
用户回答
↓
生成:
  - task/EVAL_SKILL.md
  - task/scripts/check_l0.py
  - task/scripts/check_l1.py
```

### Skill Prompt 模板

```markdown
# Evaluator Builder

你是一个评估标准定义助手。你的目标是帮助用户构建完整的评估逻辑。

## 工作流程

1. **读取 INTENT**：理解任务目标
2. **定义 L0**：识别安全边界和前置条件
3. **定义 L1**：明确机械性验证规则
4. **定义 L2**：定义质量评估标准
5. **生成输出**：Skill 文件 + 脚本

## 提问指南

### L0 - 安全/前置条件
- "什么情况下执行应该被立即终止？"
- "有什么必须存在的前提条件？"
- "有什么安全边界不能逾越？"

### L1 - 机械性验证
- "输出文件应该存在哪里？"
- "输出格式有什么硬性要求？"
- "有哪些可以用脚本验证的规则？"

### L2 - 质量验证
- "什么样的输出算'好'？"
- "有哪些主观但重要的标准？"
- "如何判断是否符合用户意图？"

## 输出格式

### EVAL_SKILL.md

```markdown
# Evaluator Skill

## L0 - 安全检查
[描述 + 脚本调用方式]

## L1 - 机械性验证
[描述 + 脚本调用方式]

## L2 - 质量验证
[LLM 评估 prompt]

## 评估流程
1. 运行 L0 检查脚本
2. 如果 L0 通过，运行 L1 检查脚本
3. 如果 L1 通过，使用 LLM 进行 L2 评估
4. 汇总结果
```

## 规则

- 三层必须都定义，即使某层为空也要显式说明
- L0/L1 优先使用脚本，L2 使用 LLM
- 脚本应该是自包含的，可独立运行
```

---

## 四、Mocker

### 设计目标

读取 Evaluator 定义，推断预期输出，生成 Mock artifacts，验证 Evaluator 逻辑。

### 输入输出

| 输入 | 输出 |
|------|------|
| `EVAL_SKILL.md` + 验证脚本 | Mock executor artifacts |

### 工作原理

```
读取 EVAL_SKILL.md
↓
推断：什么样的输出能通过 L0/L1/L2
↓
生成 Mock artifacts
↓
运行 Evaluator
↓
如果通过 → Evaluator 设计合理
如果失败 → Evaluator 可能有问题
```

### 价值

- 在真正执行前验证 Evaluator 逻辑
- 发现 Evaluator 定义的漏洞
- 提供"正确输出"的参考样本

### Skill Prompt 模板

```markdown
# Mocker

你是一个 Mock 生成助手。你的目标是根据评估标准生成符合要求的输出样本。

## 工作流程

1. **读取 Evaluator Skill**：理解 L0/L1/L2 标准
2. **读取验证脚本**：理解机械性检查逻辑
3. **推断输出**：构建能通过所有检查的 Mock 输出
4. **生成 artifacts**：写入 `run-sets/run-mock/artifacts/`

## 推断规则

### 基于 L0
- 确保不触发任何安全边界
- 满足所有前置条件

### 基于 L1
- 输出文件位置正确
- 格式完全符合规则
- 内容满足脚本验证

### 基于 L2
- 内容质量符合描述
- 风格符合预期

## 输出格式

在 `run-sets/run-mock/artifacts/` 下生成所有必要文件。

## 规则

- Mock 输出应该是"最小满足"，不要过度设计
- 如果无法生成有效 Mock，说明 Evaluator 可能定义有问题
- 生成后应自动运行 Evaluator 验证
```

---

## 五、目录结构

```
project-root/
├── task/
│   ├── INTENT.md              # INTENT Builder 输出
│   ├── EVAL_SKILL.md          # Evaluator Builder 输出
│   ├── scripts/               # Evaluator 脚本
│   │   ├── check_l0.py
│   │   └── check_l1.py
│   └── solution/              # 执行器产出
│
└── run-sets/
    ├── run-mock/              # Mocker 产出
    │   └── artifacts/
    ├── run-001/
    └── ...
```

---

## 六、实现方案

### 方案 A：Skill 文件

将 Meta Skills 实现为 Markdown Skill 文件：

```
reloop/
├── meta_skills/
│   ├── intent_builder.md
│   ├── evaluator_builder.md
│   └── mocker.md
```

### 方案 B：Python 模块

将 Meta Skills 实现为 Python 交互模块：

```
reloop/
├── meta_skills/
│   ├── __init__.py
│   ├── intent_builder.py
│   ├── evaluator_builder.py
│   └── mocker.py
```

### 推荐：方案 A

理由：
- Meta Skills 本质是 Prompt，Skill 文件更自然
- 便于用户自定义和修改
- 与 Evaluator Skill 形式一致

---

## 七、CLI 集成

```bash
# 启动 INTENT Builder
reloop init intent

# 启动 Evaluator Builder
reloop init evaluator

# 运行 Mocker 验证
reloop init mock

# 一次性初始化（引导式）
reloop init
```

---

## 八、实施步骤

### Phase 1: INTENT Builder

1. 创建 `reloop/meta_skills/intent_builder.md`
2. 实现 CLI `reloop init intent`
3. 测试生成 INTENT.md

### Phase 2: Evaluator Builder

1. 创建 `reloop/meta_skills/evaluator_builder.md`
2. 实现 CLI `reloop init evaluator`
3. 测试生成 EVAL_SKILL.md + 脚本

### Phase 3: Mocker

1. 创建 `reloop/meta_skills/mocker.md`
2. 实现 CLI `reloop init mock`
3. 测试生成 Mock artifacts + 验证

---

## 九、验收标准

### INTENT Builder

- [ ] Skill Prompt 定义完整
- [ ] CLI 命令可用
- [ ] 交互流程流畅
- [ ] 生成 INTENT.md 格式正确

### Evaluator Builder

- [ ] Skill Prompt 定义完整
- [ ] 支持 L0/L1/L2 三层定义
- [ ] 生成 EVAL_SKILL.md 格式正确
- [ ] 生成的脚本可运行

### Mocker

- [ ] Skill Prompt 定义完整
- [ ] 能读取 Evaluator 定义
- [ ] 生成的 Mock 能通过 Evaluator
- [ ] 失败时给出有用的诊断信息

---

## 参考文档

- `.discuss/2026-04-11/reloop-framework-architecture/outline.md`
- `.discuss/2026-04-11/reloop-framework-architecture/decisions/D01-reloop-framework-architecture.md`
- `.discuss/2026-04-11/reloop-framework-architecture/notes/architecture-diagram-reading.md`
