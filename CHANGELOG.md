# Changelog

## 0.1.0 — 2026-10-19

First release, with the same API coverage as the Node.js and PHP SDKs 0.4.0.

- Add `NexiomConnect` and `AsyncNexiomConnect`, which runs on asyncio and trio. Both read `NEXIOM_API_KEY` when no key is passed, and close their connections with `close()` or a `with` block.
- Add email sending, scheduled sends (`emails.reschedule`, `emails.cancel`), email logs (`emails.list`, `emails.get`), and suppressions (`emails.suppressions.list`).
- Add contact CRUD and contact property management.
- Add `templates.list`, `templates.get`, `templates.variables`, and `templates.versions` to read email templates.
- Add `domains.create`, `domains.list`, `domains.get`, `domains.verify`, and `domains.delete` to manage sending domains.
- Add `messaging.send` and `messaging.get`, one interface for every messaging channel, starting with WhatsApp template messages.
- Add `webhooks.construct_event(payload, headers, secret, tolerance=300)`, which verifies a webhook request and returns the event. `Webhooks()` works without an API key and reads headers from Django, Flask, Starlette, a `dict`, or ASGI pairs.
- Include idempotent send retries, total request deadlines that cover retries and reading the response, `Retry-After` handling, typed exceptions that can be pickled, and `TypedDict` response types that pass `mypy --strict`.
- Support Python 3.10 to 3.14 with httpx 0.27 or later and anyio 4 or later. Licensed under Apache-2.0.
