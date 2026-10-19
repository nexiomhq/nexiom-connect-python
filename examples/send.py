"""Send an email. Run with NEXIOM_API_KEY set."""

import sys

from nexiom_connect import NexiomConnect, NexiomError

with NexiomConnect() as nexiom:
    try:
        email = nexiom.emails.send(
            from_="hello@your-verified-domain.com",
            from_name="Your team",
            to="customer@example.com",
            subject="Welcome",
            html="<p>Thanks for joining us.</p>",
            text="Thanks for joining us.",
        )
    except NexiomError as error:
        sys.exit(f"{error.code or error.kind}: {error}")

    print(email["messageId"])
