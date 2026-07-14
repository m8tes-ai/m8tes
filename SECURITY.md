# Security Policy

## Reporting a vulnerability

Please **do not** open a public GitHub issue for security vulnerabilities.

Email us at **support@m8tes.ai** with:

- A description of the vulnerability and its potential impact
- Steps to reproduce (proof of concept if possible)
- Affected versions

We'll acknowledge your report within 48 hours and aim to ship a fix within 14 days for critical issues.

## Supported versions

We actively maintain the latest major version of the SDK. Security fixes are backported to the previous major version when practical.

| Version | Supported |
|---------|-----------|
| 2.x     | ✓         |
| 1.x     | security fixes when practical |
| < 1.0   | ✗         |

## Scope

In scope: the Python SDK, REST API, agent runtime, and platform infrastructure.

Out of scope: third-party integrations (Gmail, Slack, Stripe, etc.) — report those directly to the relevant vendor.
