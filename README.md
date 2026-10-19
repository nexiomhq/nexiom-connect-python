# Nexiom Connect Python SDK

The official Python SDK for Nexiom Connect. Send emails and WhatsApp messages, manage contacts, and verify webhooks from Python 3.10 or later, with a sync and an async client.

## Install

```sh
pip install nexiom-connect
```

Requires Python 3.10 or later. The only dependencies are [httpx](https://www.python-httpx.org/) and [anyio](https://anyio.readthedocs.io/). Keep your API key on the server.

## Initialize

```python
from nexiom_connect import NexiomConnect

nexiom = NexiomConnect()  # Reads the NEXIOM_API_KEY environment variable.

# Or pass the key, and optionally a custom host:
# nexiom = NexiomConnect("nc_...", base_url="https://api-connect.nxiom.com/api")
```

The client keeps connections open and is safe to share between threads: create one and reuse it. Close it with `nexiom.close()`, or use it as a context manager:

```python
with NexiomConnect() as nexiom:
    ...
```

### Async

`AsyncNexiomConnect` has the same resources and methods; await them. It runs on asyncio and trio.

```python
import asyncio

from nexiom_connect import AsyncNexiomConnect


async def main() -> None:
    async with AsyncNexiomConnect() as nexiom:
        email = await nexiom.emails.send(
            from_="hello@your-verified-domain.com",
            to="customer@example.com",
            subject="Welcome",
            text="Thanks for joining us.",
        )

        print(email["messageId"])


asyncio.run(main())
```

## Send email

Use a verified sending domain and an API key with email-send or full-access permission.

```python
from nexiom_connect import NexiomError

try:
    email = nexiom.emails.send(
        from_="hello@your-verified-domain.com",
        from_name="Your team",
        to="customer@example.com",
        subject="Welcome",
        html="<p>Thanks for joining us.</p>",
        text="Thanks for joining us.",
    )

    print(email["messageId"])
except NexiomError as error:
    print(error)
```

`from` is a Python keyword, so the sender is `from_`. Use a bare email address for `from_` and `from_name` for the display name. A successful response means the email is queued and includes `messageId`, `deliveryIds`, and `totalQueued`.

You can also send a published template with `template_id` and `template_variables`. Optional arguments include `reply_to`, `cc`, `bcc`, and `metadata`. Recipients can be one address or a list of up to 100 addresses; CC and BCC require one primary recipient.

### Idempotency

For retries across separate calls or jobs, use the same key and arguments:

```python
nexiom.emails.send(
    from_="orders@your-verified-domain.com",
    to="customer@example.com",
    subject="Order received",
    text="We received your order.",
    idempotency_key="order-123-confirmation",
)
```

Otherwise, the SDK generates a key for each call and reuses it for automatic retries. Keys contain 1–128 printable ASCII characters without whitespace. If a send fails, the key is available as `error.response.idempotency_key`, including after a timeout.

### Scheduled emails

Pass `scheduled_at` (a timezone-aware `datetime`, or an ISO 8601 timestamp with an offset, at most 30 days ahead) to send later. Use the returned `messageId` to move or cancel it before it is sent.

```python
from datetime import datetime, timedelta, timezone

email = nexiom.emails.send(
    from_="hello@your-verified-domain.com",
    to="customer@example.com",
    subject="Your trial ends tomorrow",
    text="Your trial ends tomorrow.",
    scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
)

nexiom.emails.reschedule(email["messageId"], scheduled_at="2026-10-06T09:00:00+01:00")

nexiom.emails.cancel(email["messageId"])
```

A naive `datetime` raises `NexiomValidationError`: it has no time zone, so its moment is ambiguous.

## Email logs

| Method | Description |
| --- | --- |
| `list(**filters)` | List recipient deliveries, newest first |
| `get(delivery_id)` | Get one delivery with its content and history |

Both require a full-access API key.

```python
page = nexiom.emails.list(status="bounced", limit=50)

for delivery in page["items"]:
    print(delivery["id"], delivery["recipient"], delivery["status"])

# Next page: pass page["nextCursor"] as cursor; it is None on the last page.
```

`list()` also accepts `source`, `recipient`, `search`, `contact_id`, `template_id`, `start_date`, and `end_date` (a `date`, an aware `datetime`, or an ISO 8601 string). `get()` takes a delivery ID from `deliveryIds` or `list()`, not a message ID.

### Suppressions

`emails.suppressions.list()` lists the addresses this project cannot send to, alphabetically, with the reason. It requires a full-access API key.

```python
page = nexiom.emails.suppressions.list(search="example.com", limit=50)

for suppression in page["items"]:
    print(suppression["email"], suppression["reason"])

# Next page: pass page["nextCursor"] as cursor while page["hasMore"] is true.
```

Reasons are `hard_bounce`, `complaint`, `unsubscribed`, `invalid`, `manual`, and `temporary_failure`. `search` matches part of an address.

## Contacts

Contact methods require a full-access API key.

| Method | Description |
| --- | --- |
| `create(email=..., **fields)` | Create a contact |
| `list(**filters)` | List or search contacts |
| `get(contact_id)` | Get a contact with its properties and activity |
| `update(contact_id, email=..., **fields)` | Update a contact |
| `delete(contact_id)` | Delete a contact |

```python
contact = nexiom.contacts.create(
    email="ada@example.com",
    first_name="Ada",
    last_name="Lovelace",
    properties={"company": "Example"},
)

print(contact["id"])
```

Creation also accepts `user_id` and `phone_number`. Updates require `email` and accept `email_status` (`subscribed` or `unsubscribed`); `user_id=None` clears the external user ID.

`list()` accepts `page` (up to 10,000), `limit`, `search`, `email_status`, `list_id`, and `segment_id`. It returns `items`, `total`, `page`, and `limit`, with a default page size of 50 and a maximum of 100.

Responses use the API's snake_case fields, such as `first_name` and `created_at`. Dates are ISO 8601 strings.

## Contact properties

| Method | Description |
| --- | --- |
| `create(name=..., type=..., fallback_value=...)` | Create a property |
| `list(type=..., search=...)` | List or filter properties |
| `update(property_id, name=..., type=..., fallback_value=...)` | Rename a property, change its type, or set its fallback |
| `delete(property_id)` | Delete a property |

```python
prop = nexiom.contacts.properties.create(
    name="company",
    type="string",
    fallback_value="Unknown",
)

print(prop["id"], prop["key"])
```

Types are `string`, `number`, and `date`. A type can change only while no contact has a value for the property. Fallback values are strings, or `None` to clear the fallback. Responses use `key` and `fallback_value`. The optional `type` and case-insensitive `search` filters are applied locally to the complete property list.

## Templates

Template methods are read-only and require a full-access API key. Create and edit templates in the dashboard.

| Method | Description |
| --- | --- |
| `list(**filters)` | List templates, most recently updated first |
| `get(template_id)` | Get a template with its published and draft versions |
| `variables(template_id)` | List the variables of the draft, or of the published version |
| `versions(template_id, limit=..., before_version=...)` | List versions, newest first |

```python
templates = nexiom.templates.list(status="published", limit=50)

template = nexiom.templates.get(templates["items"][0]["id"])

if template["published_version"]:
    for variable in template["published_version"]["variables"]:
        print(variable["key"], "(required)" if variable["required"] else "")
```

`list()` accepts `page`, `limit`, `status` (`draft`, `published`, `changes_in_draft`, or `archived`), `search`, `origin` (`custom` or `prebuilt`), and `category`. Sends use the published version, so `published_version["variables"]` lists exactly what a send needs. For older versions, pass the last `version_number` as `before_version`.

## Sending domains

Domain methods require a full-access API key.

| Method | Description |
| --- | --- |
| `create(domain=..., open_tracking=...)` | Add a sending subdomain and get its DNS records |
| `list(**filters)` | List sending domains |
| `get(domain_id)` | Get a domain with its DNS records |
| `verify(domain_id)` | Check the domain's DNS records now |
| `delete(domain_id)` | Delete a domain |

```python
domain = nexiom.domains.create(domain="mail.example.com")

for record in domain.get("dns_records", []):
    print(record["record_type"], record["name"], record["value"])

# After publishing the records with your DNS provider:
domain = nexiom.domains.verify(domain["id"])

print(domain["status"])
```

Sending domains must be subdomains, such as `mail.example.com`. `open_tracking` defaults to `True`. `list()` accepts `page`, `limit`, `status` (`pending`, `verified`, or `failed`), and `search`. A successful `verify()` means the check ran; read `status` before sending.

## Messaging

Send messages on a messaging channel with one method; `channel` selects the arguments. WhatsApp is the first channel. The API key needs the `whatsapp.send` or `whatsapp.full_access` permission to send WhatsApp messages.

| Method | Description |
| --- | --- |
| `messaging.send(channel=..., from_=..., to=..., template=...)` | Send a message to one recipient |
| `messaging.get(message_id)` | Get a message with its status, cost, and content |

```python
message = nexiom.messaging.send(
    channel="whatsapp",
    from_="+213555000111",
    to="+213555123456",
    template={
        "id": "mtp_your_template_id",
        "variables": {"body": {1: "Amina", 2: "A-1234"}},
    },
    idempotency_key="order-A-1234-shipped",
)

print(message["id"], message["status"])
```

For WhatsApp, `from_` is the phone number of a connected WhatsApp number and `to` the recipient, both in E.164 format. `template["id"]` is an approved template, and `template["variables"]["header"]` and `["body"]` give a string for every variable of the template, keyed by its number (`1` or `"1"`) or name (`"first_name"`). Leave `variables` out for a template without variables.

Every send carries an idempotency key; the SDK generates one when you don't pass `idempotency_key`, and it is on `error.response.idempotency_key` when a send fails. Sends are retried with the same key, so a message is sent at most once. A send with a key already used returns the original message as it is now.

A sent WhatsApp message usually has the status `accepted`: WhatsApp accepted it, which is not delivery yet. `uncertain` means WhatsApp did not confirm it; it is never resent automatically. Follow the status with `messaging.get(message_id)` or the `whatsapp.message.*` webhooks.

## Webhooks

`webhooks.construct_event(payload, headers, secret, tolerance=300)` checks a webhook request's signature and timestamp, then returns the event. It makes no network request and needs no API key: `Webhooks()` works on its own.

```python
# FastAPI
import os

from fastapi import FastAPI, Request, Response

from nexiom_connect import NexiomWebhookVerificationError, Webhooks

app = FastAPI()
webhooks = Webhooks()


@app.post("/webhooks/nexiom")
async def nexiom_webhook(request: Request) -> Response:
    try:
        event = webhooks.construct_event(
            await request.body(),
            request.headers,
            os.environ["NEXIOM_WEBHOOK_SECRET"],
        )
    except NexiomWebhookVerificationError as error:
        return Response(error.reason, status_code=400)

    if event["type"] == "email.bounced":
        print("Bounced:", event["data"]["recipient"])

    return Response(status_code=204)
```

- `payload` is the raw request body, exactly as received: `await request.body()` in FastAPI and Starlette, `request.get_data()` in Flask, or `request.body` in Django. JSON that was parsed and encoded again does not match the signature.
- `headers` accepts `request.headers` from any of those frameworks, a `dict`, or a list of `(name, value)` pairs such as ASGI's `scope["headers"]`; names are case-insensitive.
- `secret` is the endpoint's signing secret, starting with `whsec_`.
- `tolerance` is the allowed clock difference in seconds (default 300).

A request that fails verification raises `NexiomWebhookVerificationError`, whose `reason` is `missing_headers`, `invalid_timestamp`, `timestamp_out_of_tolerance`, `invalid_signature`, or `invalid_payload`. Respond `400` and do not process it.

Events are typed: checking `event["type"]` narrows `event["data"]` for type checkers. Event types added after your SDK version are still verified and returned, so handle unknown types in a default branch. Deliveries are at least once: deduplicate on `event["id"]`.

## Arguments

Every argument after a resource ID is keyword-only, with snake_case names. The SDK sends the API's field names for you (`from_name` becomes `fromName`). An unknown argument, such as `fromName` or `org_id`, raises `TypeError` instead of being ignored.

An argument left out or set to `None` is not sent, except `user_id` on contact updates and `fallback_value` on contact properties, where `None` clears the value.

## Request options

The default base URL is `https://api-connect.nxiom.com/api`. Custom URLs exclude `/v1` and use HTTPS, except for local development on loopback hosts.

Configure `timeout` (seconds, default 30), `max_retries` (default 2), or an `httpx.Client` (`httpx.AsyncClient` for the async client) as `http_client` when creating the client. Every method also accepts `timeout` and `max_retries` for one call.

```python
import httpx

nexiom = NexiomConnect(
    timeout=10,
    max_retries=3,
    http_client=httpx.Client(proxy="http://proxy.internal:8080"),
)

contacts = nexiom.contacts.list(timeout=5)
```

The timeout covers the entire request, including retries and reading the response. Reads, email and message sends, cancels, and domain verification retry network errors and HTTP 408, 429, 500, 502, 503, and 504, honoring `Retry-After`. When the wait would outlast the timeout, the SDK raises that API error at once. Reschedules, domain creation and deletion, and contact and property mutations are not automatically retried. The SDK never follows redirects, so your API key is only sent to the configured host. It never closes an `http_client` you pass in.

## Errors

Methods return the response data as plain `dict`s and `list`s. API and transport failures raise `NexiomError`:

| Attribute | Description |
| --- | --- |
| `kind` | `ErrorKind.API`, `NETWORK`, `TIMEOUT`, or `PROTOCOL` |
| `message` | The API's error message, or a description of the failure |
| `status` | HTTP status, or `None` when no response was received |
| `code` | Machine-readable API error code, such as `rate_limited` |
| `request_id` | Request ID to share with support |
| `details` | Additional API error details, such as validation failures |
| `response` | Status, headers, request ID, and the send's idempotency key |

Invalid SDK configuration or arguments raise `NexiomValidationError` (a `ValueError`) before any request is sent. Errors can be pickled, so they cross process boundaries in Celery and `multiprocessing`.

```python
from nexiom_connect import ErrorKind, NexiomError

try:
    nexiom.contacts.get("ct_123")
except NexiomError as error:
    if error.kind is ErrorKind.API and error.status == 404:
        ...  # The contact does not exist.
```

## Types

The package ships type information (`py.typed`) and passes `mypy --strict`. Response shapes are `TypedDict`s in `nexiom_connect.types`, such as `SendEmailResponse`, `Contact`, `Message`, and `WebhookEvent`, so editors complete fields and type checkers catch typos.

```python
from nexiom_connect.types import Contact


def greet(contact: Contact) -> str:
    return f"Hello, {contact['first_name'] or contact['email']}"
```

## Examples

- [Send an email](https://github.com/nexiomhq/nexiom-connect-python/blob/main/examples/send.py)
- [Send emails concurrently with the async client](https://github.com/nexiomhq/nexiom-connect-python/blob/main/examples/send_async.py)
- [Create a contact](https://github.com/nexiomhq/nexiom-connect-python/blob/main/examples/contacts.py)
- [Create a contact property](https://github.com/nexiomhq/nexiom-connect-python/blob/main/examples/contact_properties.py)
- [List published templates](https://github.com/nexiomhq/nexiom-connect-python/blob/main/examples/templates.py)
- [Add a sending domain](https://github.com/nexiomhq/nexiom-connect-python/blob/main/examples/domains.py)
- [Send a WhatsApp message](https://github.com/nexiomhq/nexiom-connect-python/blob/main/examples/messaging.py)
- [Verify a webhook request](https://github.com/nexiomhq/nexiom-connect-python/blob/main/examples/webhooks.py)

## Development

```sh
uv sync
uv run pytest
```

See [CONTRIBUTING.md](https://github.com/nexiomhq/nexiom-connect-python/blob/main/CONTRIBUTING.md).

## License

[Apache License 2.0](https://github.com/nexiomhq/nexiom-connect-python/blob/main/LICENSE). Copyright 2026 Nexiom Technologies.
