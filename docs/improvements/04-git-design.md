# Git 操作设计

## 问题背景

当前实现假设项目已是 Git 仓库，但实际场景中：
- 用户可能从空目录开始
- 可能是已有项目但未初始化 Git
- 缺乏通用的 .gitignore 模板

## 设计目标

1. **自动检测**：识别是否为 Git 仓库
2. **用户确认**：询问用户是否初始化
3. **模板支持**：提供多语言 .gitignore 模板
4. **安全操作**：避免破坏现有 Git 历史

## Git 初始化

### 检测逻辑

```python
def is_git_repo(path: Path) -> bool:
    """检测路径是否为 Git 仓库"""
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=str(path), capture_output=True
    )
    return result.returncode == 0
```

### 初始化流程

```python
def init_git_repo(path: Path) -> None:
    """初始化 Git 仓库"""
    subprocess.run(["git", "init"], cwd=str(path), check=True)
    subprocess.run(
        ["git", "config", "user.email", "reloop@example.com"],
        cwd=str(path), capture_output=True, check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Reloop Agent"],
        cwd=str(path), capture_output=True, check=True
    )
    (path / ".gitkeep").write_text("")
    subprocess.run(["git", "add", "."], cwd=str(path), check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=str(path), check=True
    )
```

### 用户交互

```python
def ensure_git_repo(path: Path, interactive: bool = True) -> bool:
    """确保路径是 Git 仓库"""
    if is_git_repo(path):
        return True
    
    if interactive:
        print("当前目录不是 Git 仓库。")
        choice = input("是否初始化 Git 仓库？[Y/n]: ").strip().lower()
        if choice not in ("", "y", "yes"):
            return False
    
    init_git_repo(path)
    logger.info(f"Git repository initialized at {path}")
    return True
```

## .gitignore 模板

### 模板库

```python
GITIGNORE_TEMPLATES = {
    "python": """
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual environments
.venv/
venv/
ENV/
env/

# Testing
.pytest_cache/
.coverage
htmlcov/
.tox/
.hypothesis/

# IDE
.idea/
.vscode/
*.swp
*.swo

# Reloop specific
run-sets/
task/solution/
logs/
""",
    "java": """
# Java
*.class
*.jar
*.war
*.ear
*.log
target/
build/
.gradle/
.idea/
*.iml

# Maven
.m2/

# Reloop specific
run-sets/
task/solution/
logs/
""",
    "go": """
# Go
*.exe
*.exe~
*.dll
*.so
*.dylib
*.test
*.out
go.sum

# Go modules
vendor/

# IDE
.idea/
.vscode/

# Reloop specific
run-sets/
task/solution/
logs/
""",
    "node": """
# Node.js
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*
.npm
.yarn-integrity

# Build
dist/
build/
.next/
out/

# IDE
.idea/
.vscode/

# Reloop specific
run-sets/
task/solution/
logs/
""",
}

DEFAULT_TEMPLATE = "python"
```

### 自动检测语言

```python
def detect_project_language(path: Path) -> str:
    """检测项目语言"""
    indicators = {
        "python": ["pyproject.toml", "setup.py", "requirements.txt", "*.py"],
        "java": ["pom.xml", "build.gradle", "*.java"],
        "go": ["go.mod", "*.go"],
        "node": ["package.json", "*.js", "*.ts"],
    }
    
    for lang, patterns in indicators.items():
        for pattern in patterns:
            if pattern.startswith("*"):
                if list(path.glob(pattern)):
                    return lang
            elif (path / pattern).exists():
                return lang
    
    return DEFAULT_TEMPLATE
```

### 生成 .gitignore

```python
def generate_gitignore(path: Path, language: str | None = None) -> None:
    """生成 .gitignore 文件"""
    if language is None:
        language = detect_project_language(path)
    
    gitignore_path = path / ".gitignore"
    
    # 不覆盖现有文件
    if gitignore_path.exists():
        logger.warning(f".gitignore already exists at {gitignore_path}")
        return
    
    template = GITIGNORE_TEMPLATES.get(language, GITIGNORE_TEMPLATES[DEFAULT_TEMPLATE])
    gitignore_path.write_text(template.strip() + "\n")
    logger.info(f"Generated .gitignore for {language}")
```

### 用户选择语言

```python
def select_language(path: Path, interactive: bool = True) -> str:
    """选择项目语言"""
    detected = detect_project_language(path)
    
    if not interactive:
        return detected
    
    print(f"检测到项目语言: {detected}")
    print("可用语言模板:")
    for i, lang in enumerate(GITIGNORE_TEMPLATES.keys(), 1):
        print(f"  [{i}] {lang}")
    print(f"  [{len(GITIGNORE_TEMPLATES) + 1}] 自定义（跳过）")
    
    choice = input(f"请选择 [1-{len(GITIGNORE_TEMPLATES) + 1}] (默认: {detected}): ").strip()
    
    if not choice:
        return detected
    
    try:
        idx = int(choice)
        if 1 <= idx <= len(GITIGNORE_TEMPLATES):
            return list(GITIGNORE_TEMPLATES.keys())[idx - 1]
    except ValueError:
        pass
    
    return detected
```

## 集成点

### CLI run 命令

```python
@app.command()
def run(
    language: str = typer.Option(
        None, "--lang", "-l", help="项目语言模板"
    ),
    no_git: bool = typer.Option(
        False, "--no-git", help="跳过 Git 初始化"
    ),
):
    """运行 Reloop 迭代循环。"""
    project_root = Path.cwd()
    
    if not no_git:
        if not ensure_git_repo(project_root):
            print("初始化 Git 仓库被取消")
            return
        
        if language:
            generate_gitignore(project_root, language)
        else:
            lang = select_language(project_root)
            generate_gitignore(project_root, lang)
    
    # 执行主循环
    # ...
```

### CLI init 命令（新增）

```python
@app.command()
def init(
    language: str = typer.Option(
        None, "--lang", "-l", help="项目语言模板"
    ),
):
    """初始化项目 Git 和配置。"""
    project_root = Path.cwd()
    
    if is_git_repo(project_root):
        print("已是 Git 仓库")
    else:
        init_git_repo(project_root)
        print("✓ Git 仓库已初始化")
    
    lang = language or select_language(project_root)
    generate_gitignore(project_root, lang)
    print(f"✓ 已生成 .gitignore ({lang})")
    
    # 创建目录结构
    (project_root / "task").mkdir(exist_ok=True)
    (project_root / "run-sets").mkdir(exist_ok=True)
    (project_root / "logs").mkdir(exist_ok=True)
    print("✓ 目录结构已创建")
```

## Reloop 专用忽略项

无论选择哪种语言模板，都应包含：

```gitignore
# Reloop specific
run-sets/          # 所有运行记录
task/solution/     # 解决方案代码
logs/              # 系统日志

# 但保留 .gitkeep
!run-sets/.gitkeep
!task/.gitkeep
!logs/.gitkeep
```

## 测试场景

| 场景 | 操作 | 预期结果 |
|------|------|----------|
| 已是 Git 仓库 | run | 跳过初始化 |
| 非 Git 仓库 + Y | run | 初始化 Git |
| 非 Git 仓库 + N | run | 取消运行 |
| 已有 .gitignore | run | 不覆盖 |
| 指定语言 | run --lang go | 使用 Go 模板 |
| 自动检测 | run | 正确检测语言 |

## 验收标准

- [ ] 正确检测 Git 仓库
- [ ] 初始化流程安全可靠
- [ ] 多语言模板完整
- [ ] 自动检测语言准确
- [ ] 不覆盖已有 .gitignore
- [ ] 交互提示清晰
- [ ] init 命令可用
- [ ] 测试覆盖所有场景
