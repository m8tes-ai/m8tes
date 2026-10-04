- A cut stream is no longer read as a finished run. When a stream ended without a
  terminal event, iteration finished normally and `stream.text` was half an answer
  that looked whole; when the connection broke, a raw `requests` exception escaped
  with no run id. Both now raise `StreamInterruptedError`, which carries `run_id` and
  says the run may still be working: wait for it with `client.runs.wait(run_id)` or
  rejoin it with `client.runs.stream(run_id)`. A stream still ends quietly on a
  terminal event, and on a run paused for an approval or a question. **Behaviour
  change:** code that read a quiet end as success now has to catch this error, and a
  test stream built with `m8tes.testing.StreamBuilder` has to end with `.done()`.
- `RunStream.run_id` is known before the metadata event: at once for `runs.stream()`
  and `runs.reply()`, and from the `X-Run-Id` response header for `runs.create()` and
  `tasks.run()`. The metadata event waits for the sandbox to boot, so a stream cut
  during boot could not say which run it was.
- `m8tes agent task`, `m8tes agent chat` and `m8tes task execute` no longer end as if
  the run were done when their stream drops. They say the connection was lost, wait
  for the run (up to 30 minutes; Ctrl+C stops waiting, not the run), then show its
  result and exit with its outcome. Before, a dropped stream printed a summary of
  half the work and exited 0, or exited 1 with "Command execution failed" while the
  run carried on.
