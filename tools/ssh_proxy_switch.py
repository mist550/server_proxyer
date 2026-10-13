"""本地 SSH 反向代理开关，管理自己启动的 SSH 进程，不修改 Git 配置。"""
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import threading
import tkinter as tk
from tkinter import filedialog,messagebox,ttk
from tkinter.scrolledtext import ScrolledText


class ProxySwitch:
    """仅在点击开启后连接服务器；配置保存地址和私钥路径，不保存密钥内容或密码。"""

    def __init__(self,root):
        self.root=root
        self.process=None
        self.stop_requested=False
        self.session=0
        self.events=queue.Queue()
        self.active_config=None
        self.config_path=Path(os.environ.get("LOCALAPPDATA",str(Path.home())))/"MRProxySwitch"/"config.json"
        defaults={
            "server":"","ssh_port":"22","username":"","private_key":"",
            "proxy_host":"127.0.0.1","proxy_port":"7897","remote_port":"17890",
            "protocol":"HTTP / Mixed",
        }
        load_error=None
        if self.config_path.exists():
            try:
                with self.config_path.open("r",encoding="utf-8") as file:
                    saved=json.load(file)
                if not isinstance(saved,dict):
                    raise ValueError("配置必须是JSON对象")
                defaults.update({key:str(saved[key]) for key in defaults if key in saved})
            except (OSError,ValueError) as error:
                load_error=str(error)
        self.values={key:tk.StringVar(value=value) for key,value in defaults.items()}
        self.status=tk.StringVar(value="未开启")
        self.git_command=tk.StringVar(value="开启隧道后，在服务器仓库目录执行复制的Git命令。")
        self.controls=[]

        root.title("SSH 代理开关")
        root.geometry("760x660")
        root.minsize(660,600)
        panel=ttk.Frame(root,padding=16)
        panel.pack(fill="both",expand=True)
        panel.columnconfigure(1,weight=1)
        fields=[
            ("server","服务器地址（不带端口）"),("ssh_port","服务器SSH端口"),
            ("username","服务器用户名"),("private_key","本地私钥路径（可留空）"),
            ("proxy_host","本地代理地址"),("proxy_port","Clash代理端口"),
            ("remote_port","服务器转发端口（仅回环监听）"),
        ]
        for row,(key,label) in enumerate(fields):
            ttk.Label(panel,text=label).grid(row=row,column=0,sticky="w",padx=(0,12),pady=4)
            entry=ttk.Entry(panel,textvariable=self.values[key])
            entry.grid(row=row,column=1,sticky="ew",pady=4)
            self.controls.append(entry)
            if key=="private_key":
                browse=ttk.Button(panel,text="浏览",command=self.browse_key)
                browse.grid(row=row,column=2,padx=(8,0))
                self.controls.append(browse)
        ttk.Label(panel,text="代理协议").grid(row=7,column=0,sticky="w",pady=4)
        self.protocol=ttk.Combobox(panel,textvariable=self.values["protocol"],
                                   values=("HTTP / Mixed","SOCKS5"),state="readonly")
        self.protocol.grid(row=7,column=1,sticky="ew",pady=4)

        buttons=ttk.Frame(panel)
        buttons.grid(row=8,column=0,columnspan=3,sticky="ew",pady=12)
        self.start_button=ttk.Button(buttons,text="开启代理隧道",command=self.start)
        self.start_button.pack(side="left")
        self.stop_button=ttk.Button(buttons,text="关闭隧道",command=self.stop,state="disabled")
        self.stop_button.pack(side="left",padx=8)
        ttk.Button(buttons,text="保存配置",command=self.save_config).pack(side="left",padx=4)
        ttk.Button(buttons,text="复制服务器Git命令",command=self.copy_command).pack(side="left",padx=4)
        self.status_label=ttk.Label(panel,textvariable=self.status,foreground="#555555")
        self.status_label.grid(row=9,column=0,columnspan=3,sticky="w")
        ttk.Entry(panel,textvariable=self.git_command,state="readonly").grid(
            row=10,column=0,columnspan=3,sticky="ew",pady=8)
        ttk.Label(panel,text=(
            "先开启Clash，端口请填写实际的HTTP / Mixed端口。隧道建立不代表GitHub一定可达。\n"
            "采用密钥/ssh-agent认证，不弹出密码输入；加密私钥需先加载到ssh-agent。\n"
            "关闭窗口会关闭隧道；电脑休眠或断网后，需要重新开启。"
        ),wraplength=710).grid(row=11,column=0,columnspan=3,sticky="w",pady=(0,8))
        self.log=ScrolledText(panel,height=12,state="disabled",wrap="word")
        self.log.grid(row=12,column=0,columnspan=3,sticky="nsew")
        panel.rowconfigure(12,weight=1)
        root.protocol("WM_DELETE_WINDOW",self.close)
        root.after(150,self.poll_events)
        if load_error:
            self.append_log(f"配置读取失败，使用默认值：{load_error}")
        self.append_log(f"配置位置：{self.config_path}；不保存私钥内容。")

    def browse_key(self):
        path=filedialog.askopenfilename(title="选择私钥文件（不是.pub文件）")
        if path:
            self.values["private_key"].set(path)

    def get_config(self):
        config={key:value.get().strip() for key,value in self.values.items()}
        if not config["server"] or any(char.isspace() for char in config["server"]) or any(
            char in config["server"] for char in "@/\\") or config["server"].startswith("-"):
            raise ValueError("服务器地址请填写IP或域名，不带用户名、路径或SSH端口")
        if not re.fullmatch(r"[A-Za-z0-9_][A-Za-z0-9_.-]*",config["username"]):
            raise ValueError("请输入有效的服务器用户名")
        for key,label in (("ssh_port","SSH端口"),("proxy_port","Clash端口"),("remote_port","转发端口")):
            if not config[key].isdigit() or not 1<=int(config[key])<=65535:
                raise ValueError(f"{label}必须是1到65535之间的整数")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+",config["proxy_host"]):
            raise ValueError("本地代理地址请填写IPv4地址或主机名，例如127.0.0.1")
        if config["protocol"] not in ("HTTP / Mixed","SOCKS5"):
            raise ValueError("请选择HTTP / Mixed或SOCKS5")
        if config["private_key"]:
            key_path=Path(config["private_key"]).expanduser()
            if not key_path.is_file() or key_path.suffix.lower()==".pub":
                raise ValueError("私钥路径不存在或选中了.pub公钥文件")
            config["private_key"]=str(key_path)
        return config

    def save_config(self):
        try:
            config=self.get_config()
            self.config_path.parent.mkdir(parents=True,exist_ok=True)
            with self.config_path.open("w",encoding="utf-8") as file:
                json.dump(config,file,ensure_ascii=False,indent=2)
            self.append_log("配置已保存。")
        except (ValueError,OSError) as error:
            messagebox.showerror("无法保存",str(error))

    def update_command(self,config):
        scheme="http" if config["protocol"]=="HTTP / Mixed" else "socks5h"
        self.git_command.set(
            f"git -c http.proxy={scheme}://127.0.0.1:{config['remote_port']} pull --ff-only")

    def copy_command(self):
        try:
            config=self.active_config if self.process and self.process.poll() is None else self.get_config()
            self.update_command(config)
            self.root.clipboard_clear()
            self.root.clipboard_append(self.git_command.get())
            self.append_log("命令已复制：请在服务器的Git仓库目录执行，不是在本地执行。")
        except ValueError as error:
            messagebox.showerror("配置错误",str(error))

    def start(self):
        if self.process and self.process.poll() is None:
            return
        try:
            config=self.get_config()
            ssh=shutil.which("ssh")
            if not ssh:
                raise ValueError("未找到ssh，请安装Windows OpenSSH客户端，并重新打开工具")
            command=[
                ssh,"-v","-N","-p",config["ssh_port"],
                "-o","BatchMode=yes","-o","StrictHostKeyChecking=yes",
                "-o","ExitOnForwardFailure=yes","-o","ConnectTimeout=15",
                "-o","ServerAliveInterval=30","-o","ServerAliveCountMax=3",
            ]
            if config["private_key"]:
                command.extend(["-i",config["private_key"],"-o","IdentitiesOnly=yes"])
            command.extend([
                "-R",f"127.0.0.1:{config['remote_port']}:{config['proxy_host']}:{config['proxy_port']}",
                f"{config['username']}@{config['server']}",
            ])
            process=subprocess.Popen(
                command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                text=True,encoding="utf-8",errors="replace",bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0,
            )
        except (ValueError,OSError) as error:
            messagebox.showerror("无法开启",str(error))
            return
        self.process=process
        self.stop_requested=False
        self.active_config=config
        self.session+=1
        self.set_running(True)
        self.status.set("正在连接服务器……")
        self.status_label.configure(foreground="#b07800")
        self.update_command(config)
        self.append_log(f"连接{config['server']}:{config['ssh_port']}，转发到本地代理{config['proxy_port']}。")
        threading.Thread(target=self.read_logs,args=(process,self.session),daemon=True).start()

    def read_logs(self,process,session):
        # 后台线程只读日志并入队，不直接操作Tk界面
        try:
            for line in process.stdout:
                self.events.put((session,"log",line.rstrip()))
        finally:
            process.stdout.close()
            self.events.put((session,"exit",process.wait()))

    def poll_events(self):
        for _ in range(200):
            try:
                session,event,value=self.events.get_nowait()
            except queue.Empty:
                break
            if session!=self.session:
                continue
            if event=="log":
                self.append_log(value)
                if "Host key verification failed" in value:
                    self.append_log("首次连接请先在本地终端用同一地址、端口登录并核对服务器指纹；本工具不自动接受未知主机。")
                elif "Permission denied" in value:
                    self.append_log("认证失败：请使用已成功登录服务器的私钥；如私钥有口令，请先加入ssh-agent。")
                if "remote forward success for:" in value:
                    self.status.set("隧道已建立 · 保持Clash和本窗口开启")
                    self.status_label.configure(foreground="#16803c")
            else:
                self.set_running(False)
                self.status.set("隧道已关闭" if self.stop_requested else f"连接已结束（退出码{value}），详情见日志")
                self.status_label.configure(foreground="#555555" if value==0 or self.stop_requested else "#b03030")
                self.process=None
                self.active_config=None
        self.root.after(150,self.poll_events)

    def set_running(self,running):
        for control in self.controls:
            control.configure(state="disabled" if running else "normal")
        self.protocol.configure(state="disabled" if running else "readonly")
        self.start_button.configure(state="disabled" if running else "normal")
        self.stop_button.configure(state="normal" if running else "disabled")

    def append_log(self,text):
        self.log.configure(state="normal")
        self.log.insert("end",text+"\n")
        # 限制窗口日志长度，避免长时间运行积累过多内容
        line_count=int(self.log.index("end-1c").split(".")[0])
        if line_count>500:
            self.log.delete("1.0",f"{line_count-500}.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    def stop(self):
        if self.process and self.process.poll() is None:
            try:
                self.stop_requested=True
                self.process.terminate()
                self.status.set("正在关闭隧道……")
            except OSError as error:
                self.append_log(f"关闭失败：{error}")

    def close(self):
        if self.process and self.process.poll() is None:
            if not messagebox.askyesno("关闭工具","关闭窗口将停止代理隧道，确定关闭吗？"):
                return
            self.stop()
        self.root.destroy()


if __name__=="__main__":
    root=tk.Tk()
    app=ProxySwitch(root)
    root.mainloop()
