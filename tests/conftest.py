from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HARNESS_SCRIPT = REPO_ROOT / "clients/python/scripts/integration-harness.mts"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "integration: live HTTP tests against AddMaple (harness or env-gated server)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if config.getoption("--run-integration", default=False):
        return
    skip_integration = pytest.mark.skip(
        reason="integration tests disabled; pass --run-integration to enable"
    )
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests (local harness or ADDMAPLE_* env vars)",
    )


@pytest.fixture(scope="session")
def integration_server() -> dict[str, str]:
    base_url = os.environ.get("ADDMAPLE_BASE_URL", "").strip()
    project_id = os.environ.get("ADDMAPLE_PROJECT_ID", "").strip()
    token = os.environ.get("ADDMAPLE_TOKEN", "").strip()

    if base_url and project_id and token:
        return {
            "mode": "live",
            "base_url": base_url,
            "project_id": project_id,
            "token": token,
        }

    if not HARNESS_SCRIPT.is_file():
        pytest.skip(f"integration harness not found at {HARNESS_SCRIPT}")

    proc = subprocess.Popen(
        ["npx", "tsx", str(HARNESS_SCRIPT)],
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    harness_url = None
    deadline = time.time() + 120
    assert proc.stdout is not None
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                break
            time.sleep(0.05)
            continue
        if "ADDMAPLE_HARNESS_READY" in line:
            harness_url = line.strip().split()[-1]
            break

    if not harness_url:
        remaining = proc.stdout.read() if proc.stdout else ""
        proc.kill()
        pytest.fail(f"integration harness failed to start:\n{remaining}")

    yield {
        "mode": "harness",
        "base_url": harness_url,
        "project_id": "integration-fixture",
        "token": "",
        "_proc": str(proc.pid),
    }

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


@pytest.fixture
def integration_config(integration_server: dict[str, str]) -> dict[str, str]:
    return integration_server
