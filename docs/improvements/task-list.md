# 开发任务清单

## 开发任务

### P0 - 核心功能

#### Logging 系统
- [ ] 实现 `StreamOutput` 类（滚动显示 + 文件写入）
- [ ] 实现 `AgentLogger` 类（带时间戳的行写入）
- [ ] 实现 `log_driver_call` 函数（记录 CLI 调用）
- [ ] 实现 `setup_system_logging` 函数（系统日志初始化）
- [ ] 在 `run_loop` 中集成四层日志系统
- [ ] 测试：日志内容完整性
- [ ] 测试：时间戳格式统一
- [ ] 测试：跨文件时间匹配

#### Checker 输出格式
- [ ] 更新 `build_checker_prompt` 使用 XML 格式
- [ ] 实现 `parse_checker_result` 支持 XML 解析
- [ ] 实现 `extract_checker_explanation` 提取解释
- [ ] 保留向后兼容（旧格式回退）
- [ ] 测试：XML 格式解析
- [ ] 测试：向后兼容
- [ ] 测试：无效输入处理

#### 中断恢复机制
- [ ] 实现 `detect_run_status` 状态检测
- [ ] 实现 `rollback_incomplete_run` 回滚逻辑
- [ ] 实现 `full_cleanup` 完全清理
- [ ] 实现 `prompt_resume_choice` 用户交互
- [ ] 在 `run_loop` 入口集成恢复逻辑
- [ ] CLI：添加 `--fresh` 参数
- [ ] 测试：状态检测
- [ ] 测试：回滚操作
- [ ] 测试：用户交互

### P1 - 重要功能

#### Git 操作
- [ ] 实现 `is_git_repo` 检测函数
- [ ] 实现 `init_git_repo` 初始化函数
- [ ] 实现 `ensure_git_repo` 用户交互函数
- [ ] 实现 `detect_project_language` 语言检测
- [ ] 实现 `generate_gitignore` 模板生成
- [ ] 添加 Python/Java/Go/Node 模板
- [ ] CLI：添加 `init` 命令
- [ ] CLI：run 命令集成 Git 初始化
- [ ] 测试：Git 检测
- [ ] 测试：初始化流程
- [ ] 测试：模板生成

#### CLI 命令
- [ ] 实现 `clean` 命令核心逻辑
- [ ] 实现 `_clean_runs` 函数
- [ ] 实现 `_clean_solution` 函数
- [ ] 实现 `_reset_git` 函数
- [ ] 实现 `_clean_logs` 函数
- [ ] 实现 `link` 命令
- [ ] 实现 `status` 命令
- [ ] CLI：添加所有命令
- [ ] 测试：clean 命令
- [ ] 测试：link 命令
- [ ] 测试：status 命令

#### Driver 流式输出
- [ ] 更新 `Driver` 基类接口（添加 `stream_callback`）
- [ ] 更新 `MockDriver` 支持流式
- [ ] 实现真实 Driver 流式读取（如 ClaudeCodeDriver）
- [ ] 在 `run_loop` 中使用流式输出
- [ ] 测试：Mock Driver 流式
- [ ] 测试：真实 Driver 流式

### P2 - 增强功能

#### Demo Run 改进
- [ ] 更新 `demo_run.py` 使用 CallbackMockDriver
- [ ] 添加真实的文件操作
- [ ] 添加流式输出演示
- [ ] 测试：Demo Run 完整性

#### 文档更新
- [ ] 更新 README.md
- [ ] 更新架构文档
- [ ] 添加使用示例

## 临时待办

- [ ] 确认 .gitignore 模板内容是否完整
- [ ] 确认 Mock Driver 流式延迟时间是否合适
- [ ] 确认日志路径格式是否用户友好
- [ ] 确认 clean 命令是否需要更细粒度选项
