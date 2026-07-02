from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_linux_installer_contains_idempotent_venv_and_demo_flow() -> None:
    script = (ROOT / "install.sh").read_text(encoding="utf-8")

    assert "python3" in script
    assert "PTCG_INSTALL_DIR" in script
    assert "venv" in script
    assert "pip install" in script
    assert "ptcg demo" in script
    assert "already installed" in script.lower()


def test_windows_installer_contains_venv_and_demo_flow() -> None:
    script = (ROOT / "install.ps1").read_text(encoding="utf-8")

    assert "PTCG_INSTALL_DIR" in script
    assert "python" in script.lower()
    assert "pip install" in script
    assert "ptcg demo" in script
    assert "Write-Host" in script
