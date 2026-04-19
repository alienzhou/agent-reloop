"""Gitignore 模板 — 多语言项目忽略规则。"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 各语言模板（包含 Reloop 专用忽略项）
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


def detect_project_language(path: Path) -> str:
    """检测项目语言。

    Args:
        path: 项目路径

    Returns:
        检测到的语言名称
    """
    logger.debug("Detecting language")
    indicators = {
        "python": ["pyproject.toml", "setup.py", "requirements.txt", "Pipfile"],
        "java": ["pom.xml", "build.gradle", "build.gradle.kts"],
        "go": ["go.mod", "go.sum"],
        "node": ["package.json", "yarn.lock", "pnpm-lock.yaml"],
    }

    # 检查文件指示器
    for lang, files in indicators.items():
        for filename in files:
            if (path / filename).exists():
                return lang

    # 检查扩展名
    for lang in indicators:
        patterns = {
            "python": "*.py",
            "java": "*.java",
            "go": "*.go",
            "node": "*.js",
        }
        if list(path.glob(patterns.get(lang, "*"))):
            return lang

    return DEFAULT_TEMPLATE


def generate_gitignore(path: Path, language: str | None = None) -> None:
    """生成 .gitignore 文件。

    Args:
        path: 项目路径
        language: 指定语言，None 则自动检测
    """
    logger.info("Generating .gitignore")
    if language is None:
        language = detect_project_language(path)

    gitignore_path = path / ".gitignore"

    # 不覆盖现有文件
    if gitignore_path.exists():
        return

    template = GITIGNORE_TEMPLATES.get(language, GITIGNORE_TEMPLATES[DEFAULT_TEMPLATE])
    gitignore_path.write_text(template.strip() + "\n", encoding="utf-8")


def get_available_languages() -> list[str]:
    """获取可用的语言模板列表。

    Returns:
        语言名称列表
    """
    return list(GITIGNORE_TEMPLATES.keys())
