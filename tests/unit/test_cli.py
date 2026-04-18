"""测试 CLI 命令。"""

import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from typer.testing import CliRunner

from reloop.cli import app, main


runner = CliRunner()


class TestInitCommand:
    """测试 init 命令。"""

    def test_init_creates_directories(self, tmp_path):
        """init 创建必要的目录结构。"""
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            result = runner.invoke(app, ["init", "--no-git"])
            
            assert result.exit_code == 0
            assert (Path(td) / "task").exists()
            assert (Path(td) / "task" / "solution").exists()
            assert (Path(td) / "run-sets").exists()
            assert (Path(td) / "logs").exists()

    def test_init_creates_git_repo(self, tmp_path):
        """init 初始化 Git 仓库。"""
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            result = runner.invoke(app, ["init"])
            
            assert result.exit_code == 0
            # 检查是否创建了 Git 仓库
            assert (Path(td) / ".git").exists()

    def test_init_with_language_option(self, tmp_path):
        """init 使用指定语言模板。"""
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            result = runner.invoke(app, ["init", "--lang", "python", "--no-git"])
            
            assert result.exit_code == 0
            gitignore = Path(td) / ".gitignore"
            assert gitignore.exists()
            content = gitignore.read_text()
            assert "__pycache__" in content

    def test_init_invalid_language(self, tmp_path):
        """init 拒绝无效语言。"""
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            result = runner.invoke(app, ["init", "--lang", "invalid"])
            
            assert result.exit_code == 1
            assert "不支持的语言" in result.output


class TestCleanCommand:
    """测试 clean 命令。"""

    def test_clean_requires_confirmation(self, tmp_path):
        """clean 需要确认。"""
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            _init_test_project(Path(td))
            
            # 不确认，直接退出
            result = runner.invoke(app, ["clean"], input="n\n")
            
            # 用户取消，不应该有错误
            assert "已取消" in result.output or result.exit_code == 0

    def test_clean_with_force(self, tmp_path):
        """clean --force 跳过确认。"""
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            project_root = Path(td)
            _init_test_project(project_root)
            
            # 创建一些 run
            run_dir = project_root / "run-sets" / "run-001"
            run_dir.mkdir(parents=True)
            (run_dir / "test.txt").write_text("test")
            
            result = runner.invoke(app, ["clean", "--force"])
            
            assert result.exit_code == 0
            assert not run_dir.exists()

    def test_clean_keep_logs(self, tmp_path):
        """clean --keep-logs 保留日志。"""
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            project_root = Path(td)
            _init_test_project(project_root)
            
            log_file = project_root / "logs" / "reloop.log"
            log_file.parent.mkdir(exist_ok=True)
            log_file.write_text("test log")
            
            result = runner.invoke(app, ["clean", "--force", "--keep-logs"])
            
            assert result.exit_code == 0
            assert log_file.exists()

    def test_clean_keep_solution(self, tmp_path):
        """clean --keep-solution 保留 solution。"""
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            project_root = Path(td)
            _init_test_project(project_root)
            
            solution_file = project_root / "task" / "solution" / "main.py"
            solution_file.parent.mkdir(parents=True, exist_ok=True)
            solution_file.write_text("# solution")
            
            result = runner.invoke(app, ["clean", "--force", "--keep-solution"])
            
            assert result.exit_code == 0
            assert solution_file.exists()


class TestLinkCommand:
    """测试 link 命令。"""

    def test_link_creates_symlink(self, tmp_path):
        """link 创建软链。"""
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            project_root = Path(td)
            target = project_root / "target_project"
            target.mkdir()
            (target / "file.txt").write_text("test")
            
            result = runner.invoke(app, ["link", str(target)])
            
            assert result.exit_code == 0
            link_path = project_root / "external" / "target_project"
            assert link_path.is_symlink()
            assert link_path.resolve() == target.resolve()

    def test_link_with_custom_name(self, tmp_path):
        """link 使用自定义名称。"""
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            project_root = Path(td)
            target = project_root / "target_project"
            target.mkdir()
            
            result = runner.invoke(app, ["link", str(target), "--name", "mylink"])
            
            assert result.exit_code == 0
            link_path = project_root / "external" / "mylink"
            assert link_path.is_symlink()

    def test_link_target_not_exists(self, tmp_path):
        """link 目标不存在时报错。"""
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            project_root = Path(td)
            target = project_root / "nonexistent"
            
            # typer 会检查 exists=True，所以会报错
            result = runner.invoke(app, ["link", str(target)])
            
            assert result.exit_code != 0


class TestStatusCommand:
    """测试 status 命令。"""

    def test_status_no_git(self, tmp_path):
        """status 显示未初始化 Git。"""
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            result = runner.invoke(app, ["status"])
            
            assert result.exit_code == 0
            assert "Git: 未初始化" in result.output

    def test_status_with_git(self, tmp_path):
        """status 显示 Git 信息。"""
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            project_root = Path(td)
            _init_git_repo(project_root)
            
            result = runner.invoke(app, ["status"])
            
            assert result.exit_code == 0
            assert "Git:" in result.output

    def test_status_shows_runs(self, tmp_path):
        """status 显示运行统计。"""
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            project_root = Path(td)
            _init_git_repo(project_root)
            
            # 创建一些 runs
            for i in range(1, 4):
                run_dir = project_root / "run-sets" / f"run-{i:03d}"
                run_dir.mkdir(parents=True)
            
            result = runner.invoke(app, ["status"])
            
            assert result.exit_code == 0
            assert "Runs: 3 次运行" in result.output


class TestRunCommand:
    """测试 run 命令。"""

    def test_run_requires_intent(self, tmp_path):
        """run 需要 INTENT 文件。"""
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            project_root = Path(td)
            _init_git_repo(project_root)
            (project_root / "task").mkdir()
            
            result = runner.invoke(app, ["run"])
            
            assert result.exit_code == 1
            assert "未找到 INTENT" in result.output

    def test_run_requires_eval_skill(self, tmp_path):
        """run 需要 EVAL_SKILL 文件。"""
        with runner.isolated_filesystem(temp_dir=tmp_path) as td:
            project_root = Path(td)
            _init_git_repo(project_root)
            (project_root / "task").mkdir()
            (project_root / "task" / "INTENT.md").write_text("test intent")
            
            result = runner.invoke(app, ["run"])
            
            assert result.exit_code == 1
            assert "未找到 Evaluator Skill" in result.output


class TestMain:
    """测试 CLI 入口点。"""

    def test_main_invokes_app(self):
        """main() 调用 app()。"""
        with patch("reloop.cli.app") as mock_app:
            main()
            mock_app.assert_called_once()


# === 辅助函数 ===

def _init_git_repo(path: Path) -> None:
    """初始化 Git 仓库。"""
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@reloop.dev"],
        cwd=path, capture_output=True, check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=path, capture_output=True, check=True
    )
    (path / ".gitkeep").write_text("")
    subprocess.run(["git", "add", "."], cwd=path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=path, capture_output=True, check=True
    )


def _init_test_project(path: Path) -> None:
    """初始化测试项目。"""
    _init_git_repo(path)
    (path / "task").mkdir(exist_ok=True)
    (path / "task" / "solution").mkdir(parents=True, exist_ok=True)
    (path / "run-sets").mkdir(exist_ok=True)
    (path / "logs").mkdir(exist_ok=True)
