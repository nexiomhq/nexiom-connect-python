"""List published templates and the variables a send needs. Run with NEXIOM_API_KEY set."""

from nexiom_connect import NexiomConnect

with NexiomConnect() as nexiom:
    page = nexiom.templates.list(status="published", limit=50)

    for item in page["items"]:
        template = nexiom.templates.get(item["id"])
        version = template["published_version"]
        variables = [variable["key"] for variable in version["variables"]] if version else []

        print(template["alias"], ", ".join(variables) or "no variables")
