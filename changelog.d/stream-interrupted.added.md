- `StreamInterruptedError` (`from m8tes import StreamInterruptedError`): the stream
  stopped before the run did. `run_id` and `reason` say which run and why; the
  underlying transport error is its `__cause__`.
