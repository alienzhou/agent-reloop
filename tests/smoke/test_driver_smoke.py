"""Driver 冒烟测试 — 极简验证各 driver 能跑通。

只发送最短 prompt（"你好"），验证：
1. CLI 命令存在且能执行
2. 返回非空响应
3. 不报错

⚠️ 这些测试会花真实的 token/API 费用，只测通就行，不要反复跑。
标记为 @pytest.mark.smoke，默认不执行，需手动指定：
    pytest tests/smoke/ -m smoke

每个 driver 设 60s 超时，防止卡死。
"""

import os

import pytest

WORKDIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
SMOKE_PROMPT = "你好，请用一句话回复。"
SMOKE_TIMEOUT = 60


@pytest.fixture
def workdir():
    """项目根目录作为工作目录"""
    return WORKDIR


class TestClaudeCodeSmoke:
    """Claude Code CLI 冒烟测试"""

    @pytest.mark.smoke
    def test_claudecode_hello(self, workdir):
        """发送最短 prompt，验证 claude -p 能执行"""
        from reloop.drivers.claudecode import ClaudeCodeDriver

        driver = ClaudeCodeDriver(
            model="sonnet",
            permission_mode="bypassPermissions",
        )
        result = driver.run(prompt=SMOKE_PROMPT, workdir=workdir, timeout=SMOKE_TIMEOUT)

        # 验证：有响应，且不为空
        assert result, "ClaudeCodeDriver 返回空响应"
        assert len(result) > 0, "ClaudeCodeDriver 返回空字符串"


class TestCursorSmoke:
    """Cursor Agent CLI 冒烟测试"""

    @pytest.mark.smoke
    def test_cursor_hello(self, workdir):
        """发送最短 prompt，验证 cursor agent -p 能执行"""
        from reloop.drivers.cursor import CursorDriver

        driver = CursorDriver(
            model="composer-2-fast",
            yolo=True,
            trust=True,
        )
        result = driver.run(prompt=SMOKE_PROMPT, workdir=workdir, timeout=SMOKE_TIMEOUT)

        # 验证：有响应，且不为空
        assert result, "CursorDriver 返回空响应"
        assert len(result) > 0, "CursorDriver 返回空字符串"


class TestCodexSmoke:
    """Codex CLI 冒烟测试"""

    @pytest.mark.smoke
    def test_codex_hello(self, workdir):
        """发送最短 prompt，验证 codex exec 能执行"""
        from reloop.drivers.codex import CodexDriver

        driver = CodexDriver(
            model="gpt-5-codex-mini",
            sandbox="workspace-write",
            full_auto=True,
        )
        result = driver.run(prompt=SMOKE_PROMPT, workdir=workdir, timeout=SMOKE_TIMEOUT)

        # 验证：有响应，且不为空
        assert result, "CodexDriver 返回空响应"
        assert len(result) > 0, "CodexDriver 返回空字符串"