# Agent-Reloop 框架改进 - 总览

## 背景

基于框架初版 Review，识别出以下核心改进方向：
1. Checker 输出格式不够稳定
2. Git 操作缺乏初始化与模板支持
3. 缺乏中断恢复机制
4. 日志系统不够完善
5. 流式输出展示体验不佳
6. 缺乏清理脚本与外部项目支持

## 改进范围

| 模块 | 改进内容 | 优先级 |
|------|----------|--------|
| Checker | 结构化输出格式（XML） | P0 |
| Logging | 四层日志系统 | P0 |
| Resume | 中断恢复机制 | P0 |
| Git | 初始化与 .gitignore 模板 | P1 |
| CLI | clean 命令、软链支持 | P1 |
| Driver | 流式输出机制 | P0 |

## 核心决策

| ID | 决策项 | 简述 |
|----|--------|------|
| D01 | Checker 格式 | XML 标签 `<checker_result>passed/failed</checker_result>` |
| D02 | 中断恢复 | 启动时提示选择，支持 `--fresh` 参数 |
| D03 | 流式显示 | 终端滚动 4 行，完整写入日志 |
| D04 | Git 初始化 | 非仓库时询问用户 |
| D05 | .gitignore | 多语言模板（Python/Java/Go/Node） |
| D06 | 清理脚本 | `reloop clean` 命令 |
| D07 | 外部软链 | 方案 A，`ln -s /path/to/project ./external/task` |
| D08 | 日志系统 | System / Driver / Agent / Prompt 四层 |
| D09 | Mock Driver | 采用真实 Driver 流式输出机制 |

## 文档索引

| 文档 | 说明 |
|------|------|
| [01-logging-design.md](./01-logging-design.md) | 日志系统详细设计 |
| [02-checker-design.md](./02-checker-design.md) | Checker 输出格式设计 |
| [03-resume-design.md](./03-resume-design.md) | 中断恢复机制设计 |
| [04-git-design.md](./04-git-design.md) | Git 操作设计 |
| [05-cli-design.md](./05-cli-design.md) | CLI 命令设计 |
| [06-driver-design.md](./06-driver-design.md) | Driver 流式输出设计 |
| [task-list.md](./task-list.md) | 开发任务清单 |
| [verification-checklist.md](./verification-checklist.md) | 验收检查清单 |
| [backlog.md](./backlog.md) | Backlog 清单 |

## 预期成果

完成本次改进后：
- Checker 判定更加可靠
- 问题排查更加高效（日志分层 + 时间戳匹配）
- 支持任务中断恢复，避免重复工作
- 支持外部项目接入
- 流式输出体验更佳
