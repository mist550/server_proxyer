# SSH 代理开关

服务器无法直接访问需要代理的网络时，通过 SSH 反向端口转发，把服务器上的代理端口连接到本地电脑的代理服务，让服务器经由本地代理访问网络。

流量路径：服务器上的 Git 等程序 → 服务器 `127.0.0.1:17890` → SSH 隧道 → 本地 `127.0.0.1:7897` 的 Clash 等代理 → 目标网络。

## 环境与依赖

| 位置 | 所需环境 |
| --- | --- |
| 本地电脑 | Windows，OpenSSH 客户端，正在运行的 Clash 等代理 |
| 本地源码启动 | Python 3.9+，带 Tkinter；没有第三方 Python 运行依赖 |
| 本地 EXE 打包 | Python 3.9+、Tkinter、`requirements-build.txt` 中的 PyInstaller |
| 服务器开关 | Linux，Bash 4.2+，可用的 `cp`、`mkdir`、`grep` 命令；不要求 Python |
| 集成检查 | Python 3.9+、pip、Bash 4.2+、curl |

`requirements.txt` 说明运行依赖；无需执行 pip 安装即可启动源码。Tkinter 随 Python 安装提供，不通过 `pip install tkinter` 安装。本地可运行 `python -m tkinter` 检查 GUI 支持，运行 `ssh -V` 检查 SSH 客户端。

服务器需要允许当前用户建立 SSH 反向端口转发，并且该用户能通过密钥或 ssh-agent 登录。无需 root 权限。

## 双击启动

- **EXE 方式**：双击 `dist/SSHProxySwitch.exe`。可以单独复制这个文件到其他 Windows 电脑使用，无需安装 Python。
- **BAT 方式**：双击根目录的 `start.bat`。它优先打开已打包的 EXE；没有 EXE 时使用 Python 3.9+ 启动 `tools/ssh_proxy_switch.py`。源码方式需要带 Tkinter 的 Python，并保留 `tools` 目录。

两种方式都需要 Windows OpenSSH 客户端（终端中的 `ssh` 命令）和本地正在运行的代理服务。EXE 不包含 SSH、Clash 或私钥。

源码仓库不包含预先生成的 EXE；需先按下文打包，才会出现 `dist/SSHProxySwitch.exe`。也可以在项目根目录直接运行：

```powershell
python tools/ssh_proxy_switch.py
```

## 使用步骤

1. 开启本地 Clash 等代理，确认实际 HTTP / Mixed 或 SOCKS5 端口。
2. 首次连接时，先在本地终端执行 `ssh -p 22 用户名@服务器地址`，核对服务器指纹并确认可以通过密钥登录。私钥带口令时，需要先加载到 ssh-agent。
3. 打开工具，填写服务器地址、SSH 端口、用户名、私钥路径和代理端口。私钥留空时使用 SSH 的默认身份文件或 ssh-agent。
4. 点击“开启代理隧道”，等状态显示隧道已建立。
5. 点击“复制服务器Git命令”，到服务器上的 Git 仓库目录执行，例如：

   ```sh
   git -c http.proxy=http://127.0.0.1:17890 pull --ff-only
   ```

   使用 SOCKS5 时，工具会生成 `socks5h://127.0.0.1:17890`。其他支持代理的程序也可以使用相应地址；本工具不会自动让服务器所有流量走代理，也不会修改全局 Git 配置。

配置保存在 `%LOCALAPPDATA%\MRProxySwitch\config.json`，只记录连接参数和私钥路径，不保存私钥内容或密码。BAT 和 EXE 共用这份配置。

请保持本地代理、工具窗口和电脑网络正常。关闭窗口会停止隧道；断网或休眠后需重新开启。服务器需允许 SSH 反向端口转发，所选远端端口不能被占用。隧道建立只说明转发成功，目标网站是否可达取决于本地代理。

## 服务器端开关（Linux / Bash）

将根目录的 `server_proxy.sh` 上传到服务器，例如放在 `~/server_proxy.sh`。在服务器 Bash 4.2+ 终端中运行：

```bash
source ~/server_proxy.sh
```

选择 `1` 开启、`0` 关闭、`s` 查看状态。开启后直接运行正常命令：

```bash
pip install 包名
curl https://目标网站
wget https://目标网站/文件
git pull
```

如果使用 Conda，可以先激活环境再开启代理：

```bash
conda activate 你的环境名
source ~/server_proxy.sh on
pip install 包名
```

`server_proxy.sh` 是设置代理环境变量的脚本，不是 Python/Conda 环境。开关返回后即可在同一终端运行程序。

也可以使用快捷开关：

```bash
source ~/server_proxy.sh on
source ~/server_proxy.sh off
```

默认使用 `http://127.0.0.1:17890`，与本地工具的默认服务器转发端口一致。本地请选择 **HTTP / Mixed** 端口；服务器开关统一使用 HTTP 代理，以兼容 pip 和 wget，HTTPS 网站也通过该 HTTP 代理访问。如果改了转发端口，只需在服务器端关闭代理后配置一次：

```bash
source ~/server_proxy.sh configure 18000
```

开关设置当前终端的大小写 HTTP/HTTPS/ALL 代理变量和 `PIP_PROXY`，绕过 localhost、127.0.0.1、::1；关闭时恢复当前终端开启前的值和导出状态。首次开启会在 `~/.bashrc` 中追加加载入口，并把脚本及开关状态保存到 `~/.config/ssh-proxy-switch/`，新开的 Bash 终端会读取开关状态。已有的其他终端和运行中的进程不会自动更新，在需要使用的终端中各自加载开关即可。登录 Bash 需由其已有的 `~/.bash_profile` 或 `~/.profile` 加载 `~/.bashrc`。

查看当前终端及新终端的开关状态：

```bash
source ~/server_proxy.sh status
```

如需卸载服务器开关，先在使用它的终端执行 `off`，然后从 `~/.bashrc` 删除 `# SSH Proxy Switch (managed loader)` 及其紧随的加载行，再删除 `~/.config/ssh-proxy-switch/`。保留 `.bashrc` 中其他配置。

必须用 `source`，`bash server_proxy.sh` 无法修改父终端。此功能适用于支持代理环境变量的程序；sudo、系统服务、容器和 Git 的 SSH 地址不在其覆盖范围内。已有的 Git 显式代理配置或工具的命令行参数可能覆盖环境变量；如果曾配置其他代理，请先检查对应配置。本工具不修改全局 Git 配置或 pip 配置文件。

代理环境变量的支持见 [pip 使用文档](https://pip.pypa.io/en/stable/user_guide/#using-a-proxy-server)、[curl 环境变量文档](https://curl.se/libcurl/c/libcurl-env.html) 和 [Wget 文档](https://www.gnu.org/software/wget/manual/wget.html#Proxies)。

开发时可运行 `python -B tests/test_server_proxy.py` 验证开关、环境恢复和代理请求。测试需要 Bash、curl 和 pip，使用项目内的临时用户目录及本机模拟代理，不修改真实用户配置。

## 重新打包 EXE

在 Windows 上准备带 Tkinter 的 Python 和 PyInstaller：

```powershell
py -3 -m pip install -r requirements-build.txt
```

双击 `build_exe.bat`，成功后输出 `dist/SSHProxySwitch.exe`。如果使用 `python` 命令管理环境，也可以运行：

```powershell
python -m pip install -r requirements-build.txt
python tools/build_exe.py
```

打包使用当前解释器的架构；分发给其他电脑时，应使用兼容的 Windows 系统和架构。打包中间产物放在临时目录，结束后自动清理，实际分发只需 EXE。

## 常见问题

| 现象 | 排查方式 |
| --- | --- |
| 找不到 SSH | 安装 Windows OpenSSH 客户端，确认 `ssh -V` 可用后重新打开工具 |
| `Host key verification failed` | 用同一服务器地址和端口在本地终端登录，核对指纹后再开启；工具不会自动接受未知主机 |
| `Permission denied` | 检查用户名、私钥和服务器授权；带口令私钥需先加载到 ssh-agent |
| 转发失败 | 检查服务器是否允许反向转发、所选转发端口是否被占用 |
| 隧道建立但 pip 无法联网 | 检查本地代理是否正常、本地是否选 HTTP / Mixed、两端的转发端口是否一致 |
| `bash server_proxy.sh` 没生效 | 在目标 Bash 终端使用 `source server_proxy.sh on` |
| 新终端没自动启用 | 检查终端是否为 Bash，以及登录配置是否加载 `.bashrc` |
| Git 仍走其他代理 | 检查已有的 Git 显式代理配置；服务器开关适用于 HTTP/HTTPS 仓库，SSH 仓库需另行配置 |

## 文件结构

```text
tools/ssh_proxy_switch.py   本地 GUI 与 SSH 隧道管理
tools/build_exe.py          Windows EXE 打包入口
start.bat                  Windows 双击启动
build_exe.bat              Windows 双击打包
server_proxy.sh            服务器端代理环境开关
tests/test_server_proxy.py  隔离环境与本机代理集成检查
requirements.txt           运行依赖说明
requirements-build.txt     可选打包依赖
```

## 开源文件

源码不预填个人用户名、服务器地址或私钥路径。个人配置保存在项目目录之外，无需随源码上传。`.gitignore` 排除了打包产物、Python 缓存、配置文件和常见私钥文件。

可以提交上述源码、依赖说明、README、LICENSE、`.gitignore` 和 `.gitattributes`。本地保存的连接配置、SSH 私钥及运行日志不随源码发布；发布前检查自行添加的文件。忽略规则不会取消已被 Git 跟踪的文件，已有仓库可用 `git ls-files` 查看实际跟踪内容。

## 许可证

本项目采用 [MIT License](LICENSE)，版权署名为 `SSH Proxy Switch contributors`。分发本项目源码或其 EXE 时，请一并保留 LICENSE 文件。打包所包含的第三方组件仍适用各自的许可证。
