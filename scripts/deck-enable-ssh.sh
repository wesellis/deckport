#!/usr/bin/env bash
#
# deck-enable-ssh.sh — turn on SSH on a Steam Deck so deckport-push can reach it.
#
# Run this ON THE DECK (Desktop Mode terminal). SteamOS updates wipe changes
# outside /home, so the sshd enable can revert after a big update — just re-run
# this. Your games, shortcuts.vdf, and grid art live in /home and survive.
#
# Park a copy on the desktop; it's a one-tap fix after an update.
set -euo pipefail

echo "deckport: enabling SSH on this Steam Deck"

# 1. The deck user needs a password before sshd will allow login.
if ! passwd -S "$USER" 2>/dev/null | grep -q ' P '; then
  echo "Set a password for user '$USER' (you'll use it from your PC):"
  passwd
else
  echo "  password already set for '$USER'"
fi

# 2. Enable + start the built-in OpenSSH server.
if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl enable --now sshd
  echo "  sshd enabled and started"
else
  echo "  systemctl not found — enable sshd manually for your distro"
fi

# 3. The drop directory deckport imports from.
mkdir -p "$HOME/Games"
echo "  drop dir ready: $HOME/Games"

ip="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo
echo "Done. From your PC:  deckport-push <game-folder> --host ${USER}@${ip:-<deck-ip>} --import"
