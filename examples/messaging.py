"""Send a WhatsApp template message. Run with NEXIOM_API_KEY set."""

import sys

from nexiom_connect import NexiomConnect, NexiomError

with NexiomConnect() as nexiom:
    try:
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
    except NexiomError as error:
        sys.exit(f"{error.code or error.kind}: {error}")

    print(message["id"], message["channel"], message["status"])
