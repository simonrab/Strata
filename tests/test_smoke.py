"""Smoke test — confirms the test suite is wired up before real work begins."""

import livemeta


def test_package_imports():
    assert livemeta.__version__ == "0.1.0"
