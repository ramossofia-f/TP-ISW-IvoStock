import shutil
import subprocess
from pathlib import Path

import pytest


def test_real_interface_notice_and_session_cleanup():
    node = shutil.which("node")
    if node is None:
        pytest.skip("La comprobación de comportamiento del frontend requiere Node.js")
    root = Path(__file__).resolve().parents[2]
    subprocess.run([node, str(root / "tests/ml/notice_harness.cjs"),
                    str(root / "src/ivostock/static/app.js")], check=True, timeout=15)
