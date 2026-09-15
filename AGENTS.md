# codex-zellij-resume

This is a public, shell-only utility. Do not add user configuration, Codex
transcripts, session-index contents, credentials, or machine-specific paths to
the repository. Keep the runtime dependency-free: POSIX `sh`, `sed`, `grep`,
and standard Unix utilities only.

The PTY proxy uses Python 3's standard library only. Run the regression suite
with `sh test/run.sh` and syntax-check it with `python3 -m py_compile
bin/codex-zellij-pty.py`.
