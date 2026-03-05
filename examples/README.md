# Examples

Runnable examples showing common m8tes patterns. Each requires `M8TES_API_KEY` set in your environment.

```bash
pip install m8tes
export M8TES_API_KEY=m8_...
python examples/revenue-report.py
```

| File | What it shows |
|------|---------------|
| [`revenue-report.py`](./revenue-report.py) | Scheduled Stripe → Slack weekly report |
| [`support-triage.py`](./support-triage.py) | Classify tickets, draft replies, escalate to Slack |
| [`customer-agent.py`](./customer-agent.py) | Multi-tenant per-user isolation with `user_id` |
| [`plan-mode.py`](./plan-mode.py) | Human approval before execution with plan review |
| [`file-report.py`](./file-report.py) | File generation and download via the API |
| [`embed-oauth.py`](./embed-oauth.py) | Embedded OAuth flow for end-user app connections |
| [`seo-monitor.py`](./seo-monitor.py) | Scheduled SEO monitoring with Search Console |

→ Full documentation at [m8tes.ai/docs](https://m8tes.ai/docs)
