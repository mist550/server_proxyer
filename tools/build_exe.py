"""Build a standalone Windows GUI executable using this Python interpreter."""

import importlib.util
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


def main():
    if sys.platform != "win32":
        print("Build the Windows executable on Windows.", file=sys.stderr)
        return 1
    if importlib.util.find_spec("PyInstaller") is None:
        print("PyInstaller is missing from this Python environment.", file=sys.stderr)
        print(f'Install it with: "{sys.executable}" -m pip install PyInstaller')
        return 1
    root = Path(__file__).resolve().parent.parent
    # Build reports contain absolute local paths; keep them out of the project.
    with TemporaryDirectory(prefix="ssh-proxy-build-") as temporary:
        command = [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm", "--clean", "--onefile", "--windowed",
            "--name", "SSHProxySwitch",
            "--distpath", str(root / "dist"),
            "--workpath", str(Path(temporary) / "pyinstaller"),
            "--specpath", temporary,
            str(root / "tools" / "ssh_proxy_switch.py"),
        ]
        return subprocess.run(command, cwd=root).returncode


if __name__ == "__main__":
    raise SystemExit(main())
