#!/usr/bin/env bash
# Source this file in Bash so the switch changes the current terminal.
if [ -z "${BASH_VERSION:-}" ]; then
    printf '%s\n' '请在 Bash 中使用：source server_proxy.sh' >&2
    return 1 2>/dev/null || exit 1
fi
if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
    printf '%s\n' '请使用 source server_proxy.sh，直接执行无法修改当前终端环境。' >&2
    exit 1
fi
if (( BASH_VERSINFO[0] < 4 || (BASH_VERSINFO[0] == 4 && BASH_VERSINFO[1] < 2) )); then
    printf '%s\n' '需要 Bash 4.2 或更新版本。' >&2
    return 1
fi

_ssh_proxy_apply() {
    local url=$1 name declaration
    local -a names=(http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY no_proxy NO_PROXY PIP_PROXY)
    # Check before making any changes, including in shells with readonly variables.
    for name in "${names[@]}"; do
        declaration=$(declare -p "$name" 2>/dev/null) || declaration=''
        if [[ $declaration =~ ^declare\ -[^\ ]*r ]]; then
            printf '无法修改只读变量：%s\n' "$name" >&2
            return 1
        fi
    done
    if [[ ${_SSH_PROXY_ACTIVE:-0} != 1 ]]; then
        declare -gA _SSH_PROXY_VALUES=() _SSH_PROXY_FLAGS=()
        for name in "${names[@]}"; do
            # A child shell may inherit our proxy without inheriting Bash arrays.
            if [[ -n ${_SSH_PROXY_URL:-} && ${!name-} == "$_SSH_PROXY_URL" ]]; then
                _SSH_PROXY_FLAGS[$name]=unset
            elif [[ -n ${_SSH_PROXY_URL:-} && ( $name == no_proxy || $name == NO_PROXY ) && ${!name-} == 'localhost,127.0.0.1,::1' ]]; then
                _SSH_PROXY_FLAGS[$name]=unset
            elif [[ -v $name ]]; then
                _SSH_PROXY_VALUES[$name]=${!name}
                declaration=$(declare -p "$name")
                if [[ $declaration =~ ^declare\ -[^\ ]*x ]]; then
                    _SSH_PROXY_FLAGS[$name]=exported
                else
                    _SSH_PROXY_FLAGS[$name]=set
                fi
            else
                _SSH_PROXY_FLAGS[$name]=unset
            fi
        done
    fi
    for name in "${names[@]}"; do
        case $name in
            no_proxy|NO_PROXY) export "$name=localhost,127.0.0.1,::1" ;;
            *) export "$name=$url" ;;
        esac
    done
    _SSH_PROXY_ACTIVE=1
    export _SSH_PROXY_URL=$url
}

_ssh_proxy_restore() {
    local name declaration
    local -a names=(http_proxy https_proxy HTTP_PROXY HTTPS_PROXY all_proxy ALL_PROXY no_proxy NO_PROXY PIP_PROXY)
    if [[ ${_SSH_PROXY_ACTIVE:-0} == 1 || -n ${_SSH_PROXY_URL:-} ]]; then
        for name in "${names[@]}"; do
            declaration=$(declare -p "$name" 2>/dev/null) || declaration=''
            if [[ $declaration =~ ^declare\ -[^\ ]*r ]]; then
                printf '无法恢复只读变量：%s\n' "$name" >&2
                return 1
            fi
        done
    fi
    for name in "${names[@]}"; do
        if [[ ${_SSH_PROXY_ACTIVE:-0} == 1 ]]; then
            case ${_SSH_PROXY_FLAGS[$name]} in
                exported) export "$name=${_SSH_PROXY_VALUES[$name]}" ;;
                set) printf -v "$name" '%s' "${_SSH_PROXY_VALUES[$name]}"; export -n "$name" ;;
                unset) unset "$name" ;;
            esac
        elif [[ -n ${_SSH_PROXY_URL:-} ]]; then
            if [[ ${!name-} == "$_SSH_PROXY_URL" || ( ( $name == no_proxy || $name == NO_PROXY ) && ${!name-} == 'localhost,127.0.0.1,::1' ) ]]; then
                unset "$name"
            fi
        fi
    done
    unset _SSH_PROXY_ACTIVE _SSH_PROXY_VALUES _SSH_PROXY_FLAGS _SSH_PROXY_URL
}

_ssh_proxy_switch() {
    local script=$1 action=${2:-menu} port=17890 choice
    local directory="$HOME/.config/ssh-proxy-switch"
    local hook='# SSH Proxy Switch (managed loader)'
    if [[ -f $directory/port ]]; then
        IFS= read -r port < "$directory/port" || return 1
    fi
    if [[ $action == configure ]]; then
        port=${3:-}
    fi
    if [[ ! $port =~ ^[0-9]{1,5}$ ]] || (( 10#$port < 1 || 10#$port > 65535 )); then
        printf '%s\n' '端口须为 1 到 65535：source server_proxy.sh configure 17890' >&2
        return 1
    fi
    port=$((10#$port))
    if [[ $action == menu ]]; then
        printf '服务器代理：%s；HTTP 端口：%s\n' "${_SSH_PROXY_URL:-当前终端未开启}" "$port"
        printf '%s\n' '1 开启   0 关闭   s 状态   q 返回'
        read -r -p '选择：' choice || return 1
        case $choice in
            1) action=on ;;
            0) action=off ;;
            s) action=status ;;
            q) return 0 ;;
            *) printf '%s\n' '无效选择。' >&2; return 1 ;;
        esac
    fi
    case $action in
        on)
            # Install a stable loader so moving the uploaded source does not break startup.
            (
                umask 077
                mkdir -p "$directory" || exit 1
                if [[ ! $script -ef $directory/switch.sh ]]; then
                    cp -- "$script" "$directory/switch.sh" || exit 1
                fi
                if ! grep -qxF "$hook" "$HOME/.bashrc" 2>/dev/null; then
                    printf '\n%s\n%s\n' "$hook" '[ ! -f "$HOME/.config/ssh-proxy-switch/switch.sh" ] || source "$HOME/.config/ssh-proxy-switch/switch.sh" --load' >> "$HOME/.bashrc" || exit 1
                fi
            ) || return 1
            _ssh_proxy_apply "http://127.0.0.1:$port" || return 1
            (umask 077; printf '%s\n' on > "$directory/enabled") || { _ssh_proxy_restore; return 1; }
            printf '代理已开启：http://127.0.0.1:%s；可直接使用 pip、curl、wget 和 HTTPS Git。\n' "$port"
            printf '%s\n' '请保持本地 SSH 隧道与 HTTP / Mixed 代理开启。'
            ;;
        off)
            _ssh_proxy_restore || return 1
            if [[ -d $directory ]]; then
                (umask 077; printf '%s\n' off > "$directory/enabled") || return 1
            fi
            printf '%s\n' '代理已关闭，当前终端恢复原环境；其他已打开终端需各自关闭。'
            ;;
        --load)
            if [[ -f $directory/enabled ]] && [[ $(< "$directory/enabled") == on ]]; then
                _ssh_proxy_apply "http://127.0.0.1:$port"
            else
                _ssh_proxy_restore
            fi
            ;;
        configure)
            if [[ ${_SSH_PROXY_ACTIVE:-0} == 1 ]] || { [[ -f $directory/enabled ]] && [[ $(< "$directory/enabled") == on ]]; }; then
                printf '%s\n' '请先关闭代理，再修改端口。' >&2
                return 1
            fi
            (umask 077; mkdir -p "$directory" && printf '%s\n' "$port" > "$directory/port") || return 1
            printf '端口已保存为 %s，以后只需开启 / 关闭。\n' "$port"
            ;;
        status)
            printf '当前终端：%s\n' "${_SSH_PROXY_URL:-未开启}"
            if [[ -f $directory/enabled ]] && [[ $(< "$directory/enabled") == on ]]; then
                printf '新 Bash 终端：开启（http://127.0.0.1:%s）\n' "$port"
            else
                printf '%s\n' '新 Bash 终端：关闭'
            fi
            printf '%s\n' '此状态表示环境配置，不代表隧道或目标网站可达。'
            ;;
        *) printf '%s\n' '用法：source server_proxy.sh [on|off|status|configure 端口]' >&2; return 1 ;;
    esac
}

_ssh_proxy_switch "${BASH_SOURCE[0]}" "$@"
