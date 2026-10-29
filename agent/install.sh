#!/bin/sh
set -eu
if ! command -v uv >/dev/null 2>&1; then
    echo 'Installez uv : pacman -S uv' >&2
    exit 1
fi
base=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
mkdir -p "$HOME/.local/share/ipp-agent" "$HOME/.config/systemd/user" "$HOME/.config/ipp-agent"
cp "$base/ipp_agent.py" "$HOME/.local/share/ipp-agent/ipp_agent.py"
cp "$base/systemd/ipp-agent.service" "$base/systemd/ipp-agent.timer" "$HOME/.config/systemd/user/"
if [ ! -e "$HOME/.config/ipp-agent/config.ini" ]; then
    (umask 077; cp "$base/config.ini.example" "$HOME/.config/ipp-agent/config.ini")
    chmod 600 "$HOME/.config/ipp-agent/config.ini"
fi
systemctl --user daemon-reload
systemctl --user enable --now ipp-agent.timer
echo 'Modifiez ~/.config/ipp-agent/config.ini puis testez :'
echo 'systemctl --user start ipp-agent.service && journalctl --user -u ipp-agent -e'
