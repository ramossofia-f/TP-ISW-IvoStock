import subprocess
import sys
from pathlib import Path


def test_verificar_documentacion_ejecuta_sin_errores():
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, str(root / "scripts" / "verificar_documentacion.py")],
        cwd=root,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert "Documentación coherente:" in result.stdout
