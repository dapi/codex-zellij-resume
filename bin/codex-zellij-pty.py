#!/usr/bin/env python3
"""PTY proxy that atomically binds a Codex thread to one Zellij pane."""
import argparse
import fcntl
import json
import os
import pty
import select
import signal
import subprocess
import sys
import termios
import threading
import time


class Registration:
    def __init__(self, marker: str):
        state = os.environ.get("XDG_STATE_HOME", os.path.expanduser("~/.local/state"))
        self.state = os.path.join(state, "codex-zellij-resume")
        self.marker_file = os.path.join(self.state, "markers", marker)
        home = os.environ.get("CODEX_HOME", os.path.expanduser("~/.codex"))
        self.index = os.path.join(home, "session_index.jsonl")
        self.done = os.path.exists(self.marker_file) and os.path.getsize(self.marker_file) > 0
        self.armed = threading.Event()

    def start(self):
        if self.done:
            return
        threading.Thread(target=self._register, daemon=True).start()
        # Snapshot the index while holding the global lock before forwarding
        # Enter to Codex. Without this barrier, Codex could write its record
        # before the proxy had established which next line belongs to this pane.
        self.armed.wait()

    def _register(self):
        os.makedirs(os.path.dirname(self.marker_file), mode=0o700, exist_ok=True)
        lock_path = os.path.join(self.state, "registration.lock")
        os.makedirs(self.state, mode=0o700, exist_ok=True)
        with open(lock_path, "a+", encoding="utf-8") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            before = self._line_count()
            self.armed.set()
            while True:
                session_id = self._line_id(before + 1)
                if session_id:
                    temp = f"{self.marker_file}.tmp.{os.getpid()}"
                    with open(temp, "w", encoding="utf-8") as output:
                        os.fchmod(output.fileno(), 0o600)
                        output.write(session_id + "\n")
                    os.replace(temp, self.marker_file)
                    self.done = True
                    return
                time.sleep(0.1)

    def _line_count(self):
        try:
            with open(self.index, encoding="utf-8") as source:
                return sum(1 for _ in source)
        except FileNotFoundError:
            return 0

    def _line_id(self, number):
        try:
            with open(self.index, encoding="utf-8") as source:
                for index, line in enumerate(source, 1):
                    if index == number:
                        value = json.loads(line).get("id")
                        return value if isinstance(value, str) and value else None
        except (FileNotFoundError, json.JSONDecodeError):
            return None
        return None


def resize(master):
    try:
        size = fcntl.ioctl(sys.stdin.fileno(), termios.TIOCGWINSZ, b"\0" * 8)
        fcntl.ioctl(master, termios.TIOCSWINSZ, size)
    except OSError:
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zellij-marker", required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command or args.command[0] != "--":
        parser.error("command must follow --")
    command = args.command[1:]
    if not command:
        parser.error("missing Codex command")

    master, slave = pty.openpty()
    resize(master)
    child = subprocess.Popen(command, stdin=slave, stdout=slave, stderr=slave, preexec_fn=os.setsid)
    os.close(slave)
    registration = Registration(args.zellij_marker)
    output_tail = b""
    stdin_open = True

    def forward_signal(signum, _frame):
        try:
            os.killpg(child.pid, signum)
        except ProcessLookupError:
            pass

    signal.signal(signal.SIGTERM, forward_signal)
    signal.signal(signal.SIGHUP, forward_signal)
    while child.poll() is None:
        inputs = [master] + ([sys.stdin.fileno()] if stdin_open else [])
        ready, _, _ = select.select(inputs, [], [], 0.2)
        if master in ready:
            try:
                data = os.read(master, 65536)
            except OSError:
                data = b""
            if data:
                os.write(sys.stdout.fileno(), data)
                output_tail = (output_tail + data)[-8192:]
        if sys.stdin.fileno() in ready:
            data = os.read(sys.stdin.fileno(), 65536)
            if not data:
                stdin_open = False
                continue
            # Ignore Enter on Codex's initial workspace-trust prompt. The next
            # Enter is the first submitted user prompt and starts registration.
            if b"\r" in data and not registration.done:
                if b"Do you trust the contents" in output_tail:
                    output_tail = b""
                else:
                    registration.start()
            try:
                os.write(master, data)
            except OSError:
                break
        resize(master)
    sys.exit(child.returncode or 0)


if __name__ == "__main__":
    main()
