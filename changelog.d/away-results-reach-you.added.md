- `Run.notified_channel` — where the run's result was delivered out of band: `"email"`
  or `"slack"`, next to `Run.notified_at`. None when nothing was sent. A run created
  with `client.runs.create(..., email_notifications=True)` now sends its result to the
  account owner when nobody has viewed it (`client.runs.mark_viewed(...)`) 5 minutes
  after it finished: a Slack DM when Slack is connected, else email.
- `client.settings.update(result_email_enabled=False, result_slack_enabled=False)` turns
  those sends off for you. Both default `True` and come back on `AccountSettings`.
