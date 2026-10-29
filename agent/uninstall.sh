#!/bin/sh
set -eu
systemctl --user disable --now ipp-agent.timer
rm -f "$HOME/.local/share/ipp-agent/ipp_agent.py" "$HOME/.config/systemd/user/ipp-agent.service" "$HOME/.config/systemd/user/ipp-agent.timer"
systemctl --user daemon-reload
echo 'Configuration conservée dans ~/.config/ipp-agent/config.ini.'
