"""Workspace 初始化和 run_id 序号的单元测试"""

from pathlib import Path

import pytest

from reloop.core.workspace import init_workspace, next_run_id


class TestNextRunId:
    """run_id 序号生成逻辑"""

    def test_empty_run_sets_returns_001(self, tmp_path):
        run_sets = tmp_path / "run-sets"
        run_sets.mkdir()
        assert next_run_id(run_sets) == "run-001"

    def test_run_sets_not_exist_returns_001(self, tmp_path):
        run_sets = tmp_path / "run-sets"
        assert next_run_id(run_sets) == "run-001"

    def test_existing_run_001_returns_002(self, tmp_path):
        run_sets = tmp_path / "run-sets"
        (run_sets / "run-001").mkdir(parents=True)
        assert next_run_id(run_sets) == "run-002"

    def test_gap_returns_max_plus_one(self, tmp_path):
        """run-001 和 run-003 存在（有 gap）→ 返回 run-004，不填 gap"""
        run_sets = tmp_path / "run-sets"
        (run_sets / "run-001").mkdir(parents=True)
        (run_sets / "run-003").mkdir(parents=True)
        assert next_run_id(run_sets) == "run-004"

    def test_zero_padded_to_three_digits(self, tmp_path):
        run_sets = tmp_path / "run-sets"
        run_sets.mkdir()
        rid = next_run_id(run_sets)
        assert rid == "run-001"
        # 数字部分恰好 3 位
        num_part = rid.split("-")[1]
        assert len(num_part) == 3

    def test_ignores_non_run_directories(self, tmp_path):
        """非 run-xxx 格式的目录不影响序号"""
        run_sets = tmp_path / "run-sets"
        (run_sets / "README.md").mkdir(parents=True)
        (run_sets / "other-dir").mkdir(parents=True)
        assert next_run_id(run_sets) == "run-001"

    def test_sequential_calls(self, tmp_path):
        """连续生成 run_id 并创建目录后，序号正确递增"""
        run_sets = tmp_path / "run-sets"
        run_sets.mkdir()
        for expected in ["run-001", "run-002", "run-003"]:
            rid = next_run_id(run_sets)
            assert rid == expected
            (run_sets / rid).mkdir()


class TestInitWorkspace:
    """init_workspace 创建目录结构"""

    def test_creates_run_directory(self, tmp_path):
        run_dir = init_workspace(tmp_path)
        assert run_dir.exists()
        assert run_dir.is_dir()

    def test_creates_logs_subdirectory(self, tmp_path):
        run_dir = init_workspace(tmp_path)
        assert (run_dir / "logs").is_dir()

    def test_no_artifacts_subdirectory(self, tmp_path):
        """artifacts 目录已移除，solution 放在 task/solution"""
        run_dir = init_workspace(tmp_path)
        assert not (run_dir / "artifacts").exists()

    def test_creates_eval_report_subdirectory(self, tmp_path):
        run_dir = init_workspace(tmp_path)
        assert (run_dir / "eval-report").is_dir()

    def test_creates_run_sets_if_not_exist(self, tmp_path):
        """run-sets/ 不存在时自动创建"""
        run_dir = init_workspace(tmp_path)
        assert (tmp_path / "run-sets").is_dir()

    def test_creates_task_solution_if_not_exist(self, tmp_path):
        """task/solution/ 不存在时自动创建"""
        init_workspace(tmp_path)
        assert (tmp_path / "task" / "solution").is_dir()

    def test_returns_correct_path(self, tmp_path):
        run_dir = init_workspace(tmp_path)
        assert run_dir.parent == tmp_path / "run-sets"
        assert run_dir.name.startswith("run-")

    def test_sequential_init_creates_incrementing_dirs(self, tmp_path):
        dir1 = init_workspace(tmp_path)
        dir2 = init_workspace(tmp_path)
        assert dir1.name == "run-001"
        assert dir2.name == "run-002"

    def test_full_sublayout(self, tmp_path):
        """验证完整的子目录结构"""
        run_dir = init_workspace(tmp_path)
        expected_subdirs = ["logs", "eval-report"]
        for sub in expected_subdirs:
            assert (run_dir / sub).is_dir(), f"{sub}/ should exist"
