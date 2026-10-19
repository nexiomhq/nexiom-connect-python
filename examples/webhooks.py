"""A webhook endpoint on the standard library's WSGI server. Run with NEXIOM_WEBHOOK_SECRET set.

In Django pass `request.body` and `request.headers`; in Flask `request.get_data()` and
`request.headers`; in FastAPI `await request.body()` and `request.headers`.
"""

import logging
import os
from collections.abc import Callable, Iterable
from typing import Any
from wsgiref.simple_server import make_server

from nexiom_connect import NexiomWebhookVerificationError, Webhooks

SECRET = os.environ["NEXIOM_WEBHOOK_SECRET"]

webhooks = Webhooks()

logger = logging.getLogger("webhooks")


def app(environ: dict[str, Any], start_response: Callable[..., Any]) -> Iterable[bytes]:
    # The exact bytes received: JSON parsed and encoded again no longer matches the signature.
    body = environ["wsgi.input"].read(int(environ.get("CONTENT_LENGTH") or 0))
    headers = {
        name[5:].replace("_", "-"): value
        for name, value in environ.items()
        if name.startswith("HTTP_")
    }

    try:
        event = webhooks.construct_event(body, headers, SECRET)
    except NexiomWebhookVerificationError as error:
        start_response("400 Bad Request", [("Content-Type", "text/plain")])

        return [error.reason.encode()]

    if event["type"] == "email.delivered":
        logger.info("Delivered to %s", event["data"]["recipient"])
    elif event["type"] == "whatsapp.message.failed":
        logger.warning("WhatsApp message failed: %s", event["data"]["failure_code"])
    else:
        logger.info("Unhandled event type %s", event["type"])

    start_response("204 No Content", [])

    return []


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    with make_server("127.0.0.1", 8000, app) as server:
        server.serve_forever()
