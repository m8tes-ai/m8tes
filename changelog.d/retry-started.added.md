- `Run.retried_by_run_id` and `Run.retried_at` name the run that started this
  one's work again, and when that run started. Both stay unset while an
  automatic retry is only queued, and when nothing has retried the run.
