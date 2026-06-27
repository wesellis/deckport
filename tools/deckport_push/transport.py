"""Build the rsync / scp / ssh commands for pushing a game to the Deck.

The command *builders* are pure (return argv lists / strings) so they're unit
testable without a Deck. Actual execution goes through :func:`run`. We shell out
to the system OpenSSH (``ssh``/``scp``, standard on Win10+/Linux/macOS) and to
``rsync`` when present — no heavyweight SSH library dependency.
"""
from __future__ import annotations

import shlex
import shutil
import subprocess

__all__ = [
    "have",
    "ssh_base",
    "mkdir_cmd",
    "rsync_cmd",
    "scp_cmd",
    "import_remote_command",
    "import_cmd",
    "run",
]


def have(tool: str) -> bool:
    return shutil.which(tool) is not None


def ssh_base(identity: str | None = None) -> list[str]:
    cmd = ["ssh"]
    if identity:
        cmd += ["-i", identity]
    return cmd


def mkdir_cmd(host: str, dest: str, identity: str | None = None) -> list[str]:
    """Ensure the remote drop dir exists before transfer.

    ``dest`` is left unquoted so the remote shell expands a leading ``~`` (keep it
    a simple path without spaces — same convention as :func:`import_remote_command`).
    """
    return ssh_base(identity) + [host, f"mkdir -p {dest}"]


def rsync_cmd(folder: str, host: str, dest: str, identity: str | None = None) -> list[str]:
    """rsync the folder (as a subdir) into ``dest`` over SSH, preserving structure."""
    ssh = "ssh" + (f" -i {shlex.quote(identity)}" if identity else "")
    # No trailing slash on the source -> the folder itself lands under dest/.
    return ["rsync", "-a", "-e", ssh, folder.rstrip("/\\"), f"{host}:{dest}/"]


def scp_cmd(folder: str, host: str, dest: str, identity: str | None = None) -> list[str]:
    """scp fallback when rsync isn't installed (scp uses the SFTP subsystem)."""
    cmd = ["scp", "-r"]
    if identity:
        cmd += ["-i", identity]
    cmd += [folder.rstrip("/\\"), f"{host}:{dest}/"]
    return cmd


def import_remote_command(dest: str, tag: str, importer: str = "~/deckport.py",
                          recipes: str | None = None) -> str:
    """The shell command run on the Deck to import after transfer.

    ``dest`` and ``importer`` are left unquoted so the remote shell expands a
    leading ``~`` (e.g. ``~/Games``) — keep them simple paths without spaces. The
    ``tag`` is shell-quoted because it normally contains a space. When ``recipes``
    is given, ``--recipes`` is added so the importer applies pinned binaries,
    launch options and Proton versions rather than only auto-detecting.
    """
    cmd = f"python3 {importer} --games-dir {dest} --tag {shlex.quote(tag)}"
    if recipes:
        cmd += f" --recipes {recipes}"
    return cmd


def import_cmd(host: str, dest: str, tag: str, importer: str = "~/deckport.py",
               identity: str | None = None, recipes: str | None = None) -> list[str]:
    return ssh_base(identity) + [host, import_remote_command(dest, tag, importer, recipes)]


def run(cmd: list[str], dry_run: bool = False) -> int:
    """Run a command (or just print it under ``dry_run``). Returns the exit code."""
    if dry_run:
        print("  $ " + " ".join(shlex.quote(c) for c in cmd))
        return 0
    return subprocess.call(cmd)
