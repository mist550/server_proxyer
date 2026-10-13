"""Exercise the server switch with an isolated HOME and a local fake proxy."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
import unittest


ROOT = Path(__file__).resolve().parents[1]
BASH = shutil.which("bash")
if os.name == "nt":
    candidate = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Git/bin/bash.exe"
    if candidate.exists():
        BASH = str(candidate)


def bash_path(path):
    value = Path(path).resolve().as_posix()
    if os.name == "nt":
        return f"/{value[0].lower()}{value[2:]}"
    return value


@unittest.skipUnless(BASH, "Bash is required")
class ServerSwitchTests(unittest.TestCase):
    def setUp(self):
        self.temporary = TemporaryDirectory(prefix="proxy-test-", dir=ROOT)
        self.addCleanup(self.temporary.cleanup)
        self.home = Path(self.temporary.name)
        self.environment = dict(os.environ)
        for name in list(self.environment):
            if name.lower().endswith("proxy") or name.startswith("_SSH_PROXY_"):
                self.environment.pop(name)
        self.environment["HOME"] = bash_path(self.home)
        self.environment["SWITCH"] = bash_path(ROOT / "server_proxy.sh")
        self.environment["TEST_PYTHON"] = bash_path(sys.executable)

    def run_bash(self, script, check=True):
        result = subprocess.run(
            [BASH, "--noprofile", "--norc", "-c", script],
            env=self.environment, cwd=ROOT, text=True,
            encoding="utf-8", errors="replace", capture_output=True, timeout=30,
        )
        if check:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def test_restore_repeated_enable_and_startup(self):
        self.run_bash('''
set -eu
printf '%s\n' '# existing config' > "$HOME/.bashrc"
export https_proxy='http://previous.invalid:8000'
http_proxy='original unexported value'
export NO_PROXY=''
source "$SWITCH" on
[[ $http_proxy == http://127.0.0.1:17890 ]]
[[ $https_proxy == "$http_proxy" && $PIP_PROXY == "$http_proxy" ]]
source "$SWITCH" on
[[ $(grep -c '^# SSH Proxy Switch (managed loader)$' "$HOME/.bashrc") == 1 ]]
bash --noprofile --norc -c 'source "$HOME/.bashrc"; [[ $http_proxy == http://127.0.0.1:17890 ]]; source "$SWITCH" off; [[ ! -v http_proxy ]]'
source "$SWITCH" off
[[ $https_proxy == http://previous.invalid:8000 ]]
[[ $http_proxy == 'original unexported value' ]]
[[ $(declare -p http_proxy) == 'declare -- '* ]]
[[ -v NO_PROXY && -z $NO_PROXY ]]
[[ ! -v HTTP_PROXY && ! -v PIP_PROXY ]]
source "$SWITCH" off
[[ $http_proxy == 'original unexported value' ]]
bash --noprofile --norc -c 'source "$HOME/.bashrc"; [[ ! -v PIP_PROXY ]]'
grep -qx '# existing config' "$HOME/.bashrc"
''')

    def test_menu_port_and_invalid_input(self):
        self.run_bash('''
set -eu
source "$SWITCH" configure 18000
source "$SWITCH" <<< 1
[[ $http_proxy == http://127.0.0.1:18000 ]]
if source "$SWITCH" configure 19000; then exit 1; fi
source "$SWITCH" <<< 0
if source "$SWITCH" configure 0; then exit 1; fi
if source "$SWITCH" configure '17890;echo bad'; then exit 1; fi
[[ $(cat "$HOME/.config/ssh-proxy-switch/port") == 18000 ]]
''')
        result = self.run_bash('bash "$SWITCH" on', check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.home / ".config/ssh-proxy-switch/enabled").read_text().strip() == "on")

    def test_readonly_does_not_partially_change_environment(self):
        self.run_bash('''
set -eu
readonly https_proxy=original
if source "$SWITCH" on; then exit 1; fi
[[ $https_proxy == original && ! -v http_proxy ]]
[[ ! -f "$HOME/.config/ssh-proxy-switch/enabled" ]]
''')

    def test_curl_and_pip_use_local_proxy(self):
        requests = []

        class Proxy(BaseHTTPRequestHandler):
            def do_GET(self):
                requests.append(("GET", self.path))
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"proxy-reached")

            def do_CONNECT(self):
                requests.append(("CONNECT", self.path))
                self.send_response(502)
                self.end_headers()

            def log_message(self, *args):
                pass

        with ThreadingHTTPServer(("127.0.0.1", 0), Proxy) as proxy:
            thread = threading.Thread(target=proxy.serve_forever, daemon=True)
            thread.start()
            try:
                self.environment["TEST_PORT"] = str(proxy.server_port)
                self.run_bash('''
set -eu
source "$SWITCH" configure "$TEST_PORT"
source "$SWITCH" on
[[ $(curl -fsS --max-time 5 http://proxy-test.invalid/probe) == proxy-reached ]]
"$TEST_PYTHON" -m pip --isolated --version > /dev/null
PIP_CONFIG_FILE=/dev/null "$TEST_PYTHON" -m pip index versions proxy-test-package --index-url https://proxy-test.invalid/simple --retries 0 --timeout 2 --disable-pip-version-check > /dev/null 2>&1 || true
source "$SWITCH" off
''')
            finally:
                proxy.shutdown()
                thread.join(timeout=5)
        self.assertIn(("GET", "http://proxy-test.invalid/probe"), requests)
        self.assertIn(("CONNECT", "proxy-test.invalid:443"), requests)

    def test_readonly_after_enable_keeps_persistent_state(self):
        self.run_bash('''
set -eu
source "$SWITCH" on
readonly https_proxy
if source "$SWITCH" off; then exit 1; fi
[[ $http_proxy == http://127.0.0.1:17890 ]]
[[ $(cat "$HOME/.config/ssh-proxy-switch/enabled") == on ]]
''')


if __name__ == "__main__":
    unittest.main(verbosity=2)
