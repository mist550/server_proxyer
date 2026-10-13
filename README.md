# SSH Proxy Switch

Let a remote server access the internet through a proxy running on your local computer. SSH reverse port forwarding connects a loopback port on the server to your local proxy service.

Traffic flow: server application (Git, pip, etc.) → server `127.0.0.1:17890` → SSH tunnel → local proxy (such as Clash) at `127.0.0.1:7897` → destination.

## Requirements

| Component | Requirements |
| --- | --- |
| Local computer | Windows, an OpenSSH client, and a running proxy service such as Clash |
| Running from source | Python 3.9+ with Tkinter; no third-party Python runtime packages |
| Building the Windows EXE | Python 3.9+, Tkinter, and PyInstaller from `requirements-build.txt` |
| Server switch | Linux, Bash 4.2+, and the `cp`, `mkdir`, and `grep` commands; Python is not required |
| Integration tests | Python 3.9+, pip, Bash 4.2+, and curl |

`requirements.txt` documents runtime requirements. No pip installation is needed to run the source. Tkinter must be provided by your Python installation or operating system; do not install it with `pip install tkinter`. Run `python -m tkinter` to check GUI support and `ssh -V` to check the SSH client.

The server must allow SSH reverse port forwarding for your account. Authentication uses an SSH key or ssh-agent. Root privileges are not required.

## Launching on Windows

- **EXE:** Double-click `dist/SSHProxySwitch.exe`. You can copy it to a compatible Windows computer without installing Python.
- **BAT:** Double-click `start.bat` in the project root. It prefers the packaged EXE when available; otherwise, it launches `tools/ssh_proxy_switch.py` using Python 3.9+. Running from source requires Tkinter and the `tools` directory.

Both methods require the `ssh` command and a running local proxy. The EXE does not bundle SSH, Clash, or private keys.

The source repository does not include a prebuilt EXE. Follow the build instructions below to generate it, or launch directly from the project root:

```powershell
python tools/ssh_proxy_switch.py
```

## Connecting the Tunnel

The current application interface is in Chinese. The instructions below describe the controls by their function.

1. Start your local proxy and identify its HTTP / Mixed or SOCKS5 port.
2. Before the first connection, run `ssh -p 22 username@server-host` in a local terminal. Verify the server fingerprint and confirm key authentication works. Load passphrase-protected keys into ssh-agent first.
3. Open the tool and enter the server address, SSH port, username, private key path, and proxy port. Leave the key field empty to use SSH's default identity files or ssh-agent.
4. Click the button to start the proxy tunnel and wait for confirmation that forwarding has been established.
5. Click the button to copy the server Git command, then run it in a Git repository **on the server**, for example:

   ```sh
   git -c http.proxy=http://127.0.0.1:17890 pull --ff-only
   ```

For SOCKS5, the tool generates `socks5h://127.0.0.1:17890`. Other applications that support proxies can use the corresponding address. The tool does not route all server traffic automatically or modify global Git configuration.

Configuration is saved to `%LOCALAPPDATA%\MRProxySwitch\config.json`. It contains connection settings and the private key path, but no private key contents or passwords. BAT and EXE launches share this configuration.

Keep your local proxy, application window, and network connection active. Closing the window stops the tunnel. Restart it after sleep or a network interruption. The selected server forwarding port must be available. An established tunnel confirms forwarding, but destination access still depends on your local proxy.

## Server Switch (Linux / Bash)

Upload `server_proxy.sh` to the server, for example as `~/server_proxy.sh`. In a Bash 4.2+ terminal on the server, run:

```bash
source ~/server_proxy.sh
```

Select `1` to enable, `0` to disable, or `s` to check status. Once enabled, run commands normally:

```bash
pip install package-name
curl https://example.com
wget https://example.com/file
git pull
```

If you use Conda, activate your environment before enabling the proxy:

```bash
conda activate your-environment
source ~/server_proxy.sh on
pip install package-name
```

`server_proxy.sh` sets proxy environment variables; it is not a Python or Conda environment. After the switch returns, run applications in the same terminal.

You can also use the switch directly:

```bash
source ~/server_proxy.sh on
source ~/server_proxy.sh off
```

The default address is `http://127.0.0.1:17890`, matching the local tool's default server forwarding port. Select an **HTTP / Mixed** proxy port in the local tool when using the server switch. It uses an HTTP proxy for compatibility with pip and wget; HTTPS destinations also use this HTTP proxy. If you change the forwarding port, disable the server proxy and configure its port once:

```bash
source ~/server_proxy.sh configure 18000
```

The switch sets lowercase and uppercase HTTP, HTTPS, and ALL proxy variables, plus `PIP_PROXY`, in the current terminal. It bypasses the proxy for `localhost`, `127.0.0.1`, and `::1`. Disabling it restores the original values and export attributes in that terminal.

The first enable operation adds a loader to `~/.bashrc` and stores the script and switch state in `~/.config/ssh-proxy-switch/`. New Bash terminals read the saved state. Other existing terminals and running processes do not update automatically; load the switch separately in each terminal where needed. Login shells must load `~/.bashrc` through their existing `~/.bash_profile` or `~/.profile`.

Check the state of the current terminal and future terminals:

```bash
source ~/server_proxy.sh status
```

To uninstall, first run `off` in terminals using the switch. Remove the `# SSH Proxy Switch (managed loader)` line and the loader line immediately following it from `~/.bashrc`, then delete `~/.config/ssh-proxy-switch/`. Preserve the rest of your Bash configuration.

Use `source`: running `bash server_proxy.sh` cannot change the parent terminal's environment. The switch applies to applications that honor proxy environment variables. It does not configure sudo, system services, containers, or Git SSH URLs. Explicit Git proxy settings or application command-line options may override environment variables; check existing proxy configuration if necessary. The tool does not modify global Git or pip configuration files.

For proxy environment variable support, see the [pip documentation](https://pip.pypa.io/en/stable/user_guide/#using-a-proxy-server), [curl documentation](https://curl.se/libcurl/c/libcurl-env.html), and [Wget documentation](https://www.gnu.org/software/wget/manual/wget.html#Proxies).

## Integration Tests

Run from the project root:

```bash
python -B tests/test_server_proxy.py
```

The tests cover switching, environment restoration, and proxy requests. They require Bash, curl, and pip, and use temporary user directories inside the project and a local mock proxy. They do not modify your real user configuration.

## Building the Windows EXE

On Windows, use Python with Tkinter and install the build dependencies:

```powershell
py -3 -m pip install -r requirements-build.txt
```

Double-click `build_exe.bat`. A successful build produces `dist/SSHProxySwitch.exe`. If you manage your environment with the `python` command, you can also run:

```powershell
python -m pip install -r requirements-build.txt
python tools/build_exe.py
```

The build uses the current Python interpreter's architecture. Distribute it to a compatible Windows system and architecture. Intermediate files are stored in a temporary directory and cleaned up when the build finishes. Distribute the EXE together with the license notices described below.

## Troubleshooting

| Issue | What to check |
| --- | --- |
| SSH not found | Install the Windows OpenSSH client, verify `ssh -V`, and reopen the tool |
| `Host key verification failed` | Log in locally with the same server address and port and verify the fingerprint; the tool does not automatically accept unknown hosts |
| `Permission denied` | Check the username, private key, and server authorization; load passphrase-protected keys into ssh-agent |
| Forwarding fails | Check server permissions for reverse forwarding and whether the forwarding port is occupied |
| Tunnel established but pip cannot connect | Check the local proxy, select HTTP / Mixed, and ensure both sides use the same forwarding port |
| `bash server_proxy.sh` has no effect | Use `source server_proxy.sh on` in the target Bash terminal |
| New terminals do not enable the proxy | Check that the shell is Bash and its login configuration loads `.bashrc` |
| Git still uses another proxy | Check explicit Git proxy settings; the switch supports HTTP/HTTPS repositories, while SSH repositories need separate configuration |

## Project Structure

```text
tools/ssh_proxy_switch.py   Local GUI and SSH tunnel management
tools/build_exe.py          Windows EXE build entry point
start.bat                  Windows launcher
build_exe.bat              Windows build launcher
server_proxy.sh            Server proxy environment switch
tests/test_server_proxy.py  Isolated environment and local proxy tests
requirements.txt           Runtime dependency notes
requirements-build.txt     Optional build dependencies
```

## Publishing the Source

The source does not prefill personal usernames, server addresses, or private key paths. Personal configuration is stored outside the project directory and is not needed for publication. `.gitignore` excludes build artifacts, Python caches, configuration files, and common private key files.

Commit the source files, dependency files, README, LICENSE, `.gitignore`, and `.gitattributes`. Keep saved connection settings, SSH private keys, and runtime logs out of the published source, and review any files you add yourself. Ignore rules do not untrack files already tracked; use `git ls-files` to inspect tracked files in an existing repository.

## License

This project is licensed under the [MIT License](LICENSE), with the copyright attribution `SSH Proxy Switch contributors`. Include the LICENSE file when distributing the source or its EXE. Third-party components included in a packaged application remain subject to their own licenses.
