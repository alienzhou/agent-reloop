# Agent-Reloop 框架改进讨论

## 🔵 当前焦点
（讨论已完成）

## ✅ 已确认

### D01 - Checker 输出格式
**决策**: 采用 XML 标签方案 + 可选解释
```xml
<checker_result>passed</checker_result>

[Optional: Brief explanation]
```
**理由**: 
- LLM 输出 XML 比 JSON 更可靠
- 便于解析，在单独行上匹配
- 允许输出解释内容，增强可理解性
- Checker 是任务无关的通用分类器

### D02 - 中断恢复机制
**决策**: 
1. 启动时检测是否有未完成的 run，提示用户选择：
   - "继续运行"（默认）
   - "完全回滚从头运行"
2. 支持交互式输入 + 参数控制：`--fresh` 强制从头
3. 回滚包含：Git reset + 目录删除

### D03 - 流式输出显示
**决策**: 
- 终端滚动显示最近 4 行（可配置变量）
- 完整日志写入 `run-sets/run-XXX/logs/`

### D04 - Git 初始化
**决策**: 检测到非 Git 仓库时询问用户是否初始化

### D05 - .gitignore 模板
**决策**: 支持多语言模板（Python/Java/Go/Node.js），自动检测或让用户选择

### D06 - 清理脚本
**决策**: `reloop clean` 命令，清理：
- 所有 run-sets/ 下 runs
- task/solution/ 内容
- Git 回滚到初始状态

### D07 - 外部项目软链
**决策**: 采用方案 A（软链）
- `ln -s /path/to/project ./external/task`
- 支持外部项目直接接入 reloop 迭代

### D08 - 日志系统设计
**决策**: 四层日志结构
- **System Log** (`logs/reloop.log`): 全局框架日志，跨 run
- **Driver Log** (`run-sets/run-XXX/logs/driver.log`): CLI 调用记录（命令、参数、返回码、耗时）
- **Agent Log** (`run-sets/run-XXX/logs/{executor,evaluator,checker}.log`): Agent 完整输出
- **Prompt Log** (`run-sets/run-XXX/logs/prompt.log`): 发送的完整 prompt

统一前缀格式：`YYYY-MM-DD HH:mm:ss.SSS [LEVEL] [module.path] message`

### D09 - Mock Driver 改进
**决策**: Mock Driver 采用与真实 Driver 相同的流式输出机制
- 终端滚动显示最近 4 行（可配置）
- 完整输出写入 Agent Log
- 提供路径提示，方便用户查看完整日志

**理由**: 使测试更真实，验证流式输出机制的正确性

## ⚪ 待讨论
（所有问题已讨论完毕）

## ✅ 已确认
(初始为空)

## ❌ 已拒绝
(初始为空)

## 📝 问题清单

### 1. Checker 输出格式
**问题描述**: 当前实现解析 PASS/FAILED 文本，可能不够稳定。用户建议定义更格式化的输出方式。

### 2. Git 操作
**问题描述**: 
- 当前目录不一定是 Git 目录，需要初始化
- 需要通用的 .gitignore 模板处理依赖

### 3. 中断与恢复机制
**问题描述**: 任务中断后需要能从上次状态继续。例如：运行了1、2、3，如果3未完成，下次应回滚到3之前状态重新运行。可能需要快照机制。

### 4. Demo Run 测试完整性
**问题描述**: 运行 Demo Run 后未看到目录或产出变化，只有终端打印。Mock 是否足够真实？

### 5. 清理脚本
**问题描述**: 需要一个快捷脚本将系统回滚到原始状态，清理快照和运行内容。

### 6. 外部项目软链
**问题描述**: 很多任务是单独项目或独立目录。是否可以软链某些内容，让产出直接在另一个项目中？

### 7. 提示词 Review
**问题描述**: 需要 Executor、Evaluator、Checker 三个提示词的完整构建示例供 Review。

### 8. 流式输出展示
**问题描述**: Driver 的流式输出直接显示在终端会铺得很长。建议：
- 终端滚动输出，只显示一定数量字符
- 同时存储到 RUN 日志
- 提供辅助提示信息，告诉用户可以 tail 哪个路径查看完整记录
- Mock Driver 也采用类似机制
