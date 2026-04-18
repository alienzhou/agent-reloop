import os

import pytest


def pytest_collection_modifyitems(config, items):
    """跳过 real_agent 测试，除非 RELOOP_TEST_REAL_AGENT=1"""
    if os.environ.get("RELOOP_TEST_REAL_AGENT") == "1":
        return
    skip_real = pytest.mark.skip(reason="need RELOOP_TEST_REAL_AGENT=1 to run")
    for item in items:
        if "real_agent" in item.keywords:
            item.add_marker(skip_real)
