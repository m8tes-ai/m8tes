- `skills.list_invokable(teammate_id=...)` also returns the skills committed in the
  repository the teammate is bound to, as `InvokableSkill(kind="repo")`. `skill=` on
  `runs.create` / `runs.reply` accepts one of them, like a saved skill. An unknown slug
  is still a 422; when the repository cannot be read from GitHub an explicit `skill=`
  raises the 503 error. An idempotent request is retried on this client's own
  backoff; it does not wait out the `Retry-After` on that 503.
