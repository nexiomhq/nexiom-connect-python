"""Create a contact property. Run with NEXIOM_API_KEY set."""

from nexiom_connect import NexiomConnect

with NexiomConnect() as nexiom:
    prop = nexiom.contacts.properties.create(
        name="company",
        type="string",
        fallback_value="Unknown",
    )

    print(prop["id"], prop["key"])
