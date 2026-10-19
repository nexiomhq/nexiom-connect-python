"""Create a contact. Run with NEXIOM_API_KEY set."""

from nexiom_connect import NexiomConnect

with NexiomConnect() as nexiom:
    contact = nexiom.contacts.create(
        email="ada@example.com",
        first_name="Ada",
        last_name="Lovelace",
        properties={"company": "Example"},
    )

    print(contact["id"], contact["email_status"])
