"""Send emails concurrently with the async client. Run with NEXIOM_API_KEY set."""

import asyncio

from nexiom_connect import AsyncNexiomConnect


async def main() -> None:
    async with AsyncNexiomConnect() as nexiom:
        emails = await asyncio.gather(
            *(
                nexiom.emails.send(
                    from_="hello@your-verified-domain.com",
                    to=address,
                    subject="Welcome",
                    text="Thanks for joining us.",
                    idempotency_key=f"welcome-{address}",
                )
                for address in ("ada@example.com", "grace@example.com")
            ),
        )

    for email in emails:
        print(email["messageId"])


asyncio.run(main())
