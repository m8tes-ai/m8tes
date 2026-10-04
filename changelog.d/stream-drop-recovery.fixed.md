- The wait after a dropped stream reports how the run really stands. `m8tes agent task`
  and `m8tes task execute` exit non-zero on a run that ended `cancelled` or `closed`,
  and `m8tes agent chat` says the turn did not answer instead of going back to the
  prompt. A run that pauses on an approval or a question is put to you when you are at
  the terminal. In json output, or with stdin piped, the wait stops there and decides
  nothing: the task commands exit non-zero saying the run is paused and has not
  finished, and chat says so and goes on. A reply queued behind a turn that was still
  running waits for its own turn (`RunStream.await_queued_message_id`), not the one in
  front of it. The README wait example uses a timeout long enough for a long run.
- A second attempt on the same stream is no longer read as finished. A run that fails
  on one model provider is started again on the next, on the same response. A cut during
  that second attempt now raises `StreamInterruptedError`.
- An idempotent replay whose body stalls or is cut raises `StreamInterruptedError` with
  the run id (from the call, the `X-Run-Id` header, or the body once its id has arrived
  whole) instead of a raw `requests` error that names no run.
