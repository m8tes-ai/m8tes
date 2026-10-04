- A recovered run no longer raises `RunFailedError`. `error_cleared` clears
  `stream.errors` after the attempt that finished, so `raise_on_error=True` does
  not raise. The failed attempt's own `done`, a snapshot, or any other frame does
  not clear the error.
