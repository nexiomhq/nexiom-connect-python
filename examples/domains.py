"""Add a sending domain and print the DNS records to publish. Run with NEXIOM_API_KEY set."""

from nexiom_connect import NexiomConnect

with NexiomConnect() as nexiom:
    domain = nexiom.domains.create(domain="mail.example.com")

    for record in domain.get("dns_records", []):
        print(record["record_type"], record["name"], record["value"])

    # After publishing the records with your DNS provider:
    domain = nexiom.domains.verify(domain["id"])

    print(domain["status"])
