# codex-zellij-resume

Reliable per-pane [Codex CLI](https://developers.openai.com/codex/) session
recovery for [Zellij](https://zellij.dev/). It keeps several Codex panes in
the same working directory attached to their own conversations after a Zellij
crash, an intentional quit, or a reboot.

Zellij restores commands, not process memory. `codex resume --last` is unsafe
when multiple panes share a directory because it identifies the latest session
for that directory, rather than the session that belonged to one particular
pane. This utility writes a private, local mapping from a generated marker to
the exact Codex session ID and teaches Zellij how to use it when resurrecting a
pane.

## Install

```sh
git clone https://github.com/dapi/codex-zellij-resume.git
cd codex-zellij-resume
install -m 755 bin/codex-zellij ~/.local/bin/codex-zellij
install -m 755 bin/zellij-codex-resurrect ~/.local/bin/zellij-codex-resurrect
```

Add this to `~/.config/zellij/config.kdl` (replace the path if necessary):

```kdl
session_serialization true
post_command_discovery_hook "~/.local/bin/zellij-codex-resurrect"
```

Start interactive panes with `codex-zellij`, not bare `codex`:

```sh
codex-zellij
codex-zellij -C ~/code/my-project
```

After an exit or reboot, resurrect normally:

```sh
zellij attach my-session
```

Zellij asks before rerunning commands by default. Review them and press Enter,
or use `zellij attach --force-run-commands my-session` only when that is safe
for every pane in the session.

## How it works

1. `codex-zellij` re-execs itself with a unique marker so Zellij serializes it
   with the pane command.
2. It holds a short local registration lock while Codex adds the next record to
   `~/.codex/session_index.jsonl`, then atomically saves `marker → session ID`
   in `~/.local/state/codex-zellij-resume/markers/`.
3. On resurrection, Zellij supplies the serialized command as
   `$RESURRECT_COMMAND`. `zellij-codex-resurrect` finds the marker and emits
   `codex resume <exact-id> --no-alt-screen`.

The lock is intentional. The Codex session index contains no pane or process
ID, so it is the only portable way to bind a newly created session to the pane
that launched it. Use `codex-zellij` for every interactive Codex pane in a
given account while using this tool; a concurrent bare `codex` launch can
otherwise enter the same index between the wrapper's snapshot and Codex's
record.

The registration watcher waits until the first message creates the Codex
session record; it does not expire while the interactive pane is still open.

If a crash happens before Codex has written its index record, the pane starts a
new Codex session instead of guessing with `--last`.

## Limitations

- A running tool or command cannot be resumed; Codex resumes the conversation,
  not the interrupted subprocess.
- Do not use the tool for `codex exec`, `review`, login, or other
  non-interactive subcommands; they deliberately pass through unchanged.
- If Codex gains a supported way to provide a session ID at session creation,
  this index-based registration should be replaced with that API.

## Test

```sh
sh test/run.sh
```

For a real local smoke test that starts two fresh interactive Codex panes in
one directory, use the included isolated Zellij configuration. It does not
modify your normal Zellij configuration:

```sh
zellij --config test/zellij-smoke.config.kdl \
  --session codex-zellij-smoke --layout test/zellij-smoke.kdl
```

Quit the test session, then attach to it again with the same command and
`--force-run-commands` to verify both panes resume independently. Delete the
test session afterwards with `zellij delete-session codex-zellij-smoke`.

## License

[MIT](LICENSE)
