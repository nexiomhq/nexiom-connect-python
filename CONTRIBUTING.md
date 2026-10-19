# Contributing to the Nexiom Connect Python SDK

Thanks for contributing to **`nexiom-connect`**, the official Python SDK from Nexiom Technologies.

**License:** [Apache License 2.0](./LICENSE).

For installation and usage, see the [README](./README.md) and [examples](./examples).

## Development setup

Requires **[uv](https://docs.astral.sh/uv/)**. uv installs the Python versions and dependencies the project needs.

Fork the repository, clone your fork, and create a branch for your change:

```sh
git clone git@github.com:YOUR_USERNAME/nexiom-connect-python.git
cd nexiom-connect-python
git switch -c fix/describe-your-change

uv sync
uv run pytest
```

| Command | Purpose |
| --- | --- |
| `uv run pytest` | Run the test suite against the sync and async clients |
| `uv run mypy` | Type-check the source, tests, examples, and `tests/typecheck/consumer.py` with `--strict` |
| `uv run ruff check` | Lint |
| `uv run ruff format` | Format |
| `uv run --python 3.14 pytest` | Run the tests on another Python version |
| `uv build` | Build the wheel and source distribution into `dist/` |

CI runs the tests on Python **3.10, 3.11, 3.12, 3.13, and 3.14**, and again on Python 3.10 with the lowest supported dependencies (`uv sync --resolution lowest-direct`). It also lints, type-checks, builds the package, checks its metadata with `twine check --strict`, and imports the built wheel in a clean environment. Tests use an in-process httpx `MockTransport` and a local HTTP server; they do not require an API key or a live account.

Read [tests/failure-scenarios.md](./tests/failure-scenarios.md) before changing behavior. Add the scenario there first, then the code, then the test that covers it.

## Project layout

```text
src/nexiom_connect/
  __init__.py              # Public exports
  _version.py              # __version__, the single source of the package version
  _client.py               # NexiomConnect and AsyncNexiomConnect
  _errors.py               # NexiomError, ErrorKind, ResponseMetadata, and the other exceptions
  _transport.py            # HTTP transport: authentication, retries, deadlines, response parsing
  _validate.py             # Shared argument validation and NOT_GIVEN
  types.py                 # TypedDict responses, parameters, and webhook events (public)
  _resources/
    emails.py              # Sending, scheduling, email logs, and suppressions
    contacts.py            # Contacts and contact properties
    templates.py           # Templates, variables, and versions (read-only)
    domains.py             # Sending domains
    messaging.py           # Messages on every channel
    webhooks.py            # Webhook verification
tests/
  failure-scenarios.md     # Every failure mode and the test that covers it
  conftest.py              # Recording fake API, run against both clients
  test_*.py                # Resource contracts, transport behavior, validation
  typecheck/consumer.py    # How users see the types; checked by mypy, never run
examples/                  # Public usage examples
```

Each resource module builds a transport-independent `Request` in private functions, and its sync and async classes only send it. Put validation and request building in those functions so both clients behave the same.

## Supported resources

Keep changes within the SDK's supported API surface unless a new feature has been agreed on in an issue. The Node.js and PHP SDKs cover the same surface.

| Resource | Methods |
| --- | --- |
| `nexiom.emails` | `send(...)`, `cancel(message_id)`, `reschedule(message_id, scheduled_at=...)`, `list(...)`, `get(delivery_id)` |
| `nexiom.emails.suppressions` | `list(...)` |
| `nexiom.contacts` | `create(...)`, `list(...)`, `get(contact_id)`, `update(contact_id, ...)`, `delete(contact_id)` |
| `nexiom.contacts.properties` | `create(...)`, `list(...)`, `update(property_id, ...)`, `delete(property_id)` |
| `nexiom.templates` | `list(...)`, `get(template_id)`, `variables(template_id)`, `versions(template_id, ...)` |
| `nexiom.domains` | `create(...)`, `list(...)`, `get(domain_id)`, `verify(domain_id)`, `delete(domain_id)` |
| `nexiom.messaging` | `send(...)`, `get(message_id)` |
| `nexiom.webhooks` | `construct_event(payload, headers, secret, tolerance=300)` |

Every method accepts `timeout` and `max_retries`. Email and message sends also accept `idempotency_key`.

## Conventions

| Topic | Convention |
| --- | --- |
| Initialization | `NexiomConnect(api_key=None, *, base_url=..., timeout=..., max_retries=..., http_client=...)`; the key falls back to `NEXIOM_API_KEY` |
| Sync and async | Every method exists on both clients with the same signature; the async one is awaited |
| Base URL | Defaults to `https://api-connect.nxiom.com/api`; versioned paths belong to each resource |
| Authentication | Bearer API key; do not add organization or project scope arguments |
| Arguments | Keyword-only, snake_case, mapped to the API's names; `from` is `from_`; Python refuses unknown names |
| `None` | Means "not sent", except where the API uses `null` to clear a value: those arguments default to `NOT_GIVEN` |
| Results | Methods return the API's data as `dict`s and `list`s, typed with `TypedDict`s in `types.py` |
| Errors | API and transport failures raise `NexiomError`; invalid arguments raise `NexiomValidationError` before a request |
| Response fields | Preserve the API's field names, including snake_case and camelCase fields; dates remain ISO 8601 strings |
| Retries | Retry reads, idempotent sends, cancels, and domain verification only; reuse the send's key across attempts |
| Regular expressions | Use `fullmatch` with `re.ASCII`: `$` also matches before a trailing newline, and `\d` matches non-ASCII digits |
| Secrets | Never keep the API key where `repr()`, `vars()`, a traceback's locals, or an exception's `__context__` can reach it |
| Internals | Modules starting with `_` may change in any release; only names exported from `nexiom_connect` and `nexiom_connect.types` are public |
| Dependencies | httpx and anyio are the only runtime dependencies |

Format with `ruff format` (line length 100). Separate functions and logical blocks with blank lines, and prefer a named result followed by a clear return. Keep examples short, readable, and focused on one action.

## Releasing

Releases are handled by maintainers. The package version, Git tag, GitHub Release, and PyPI version must agree: `0.1.1` → `v0.1.1` → `nexiom-connect==0.1.1`.

1. In one pull request, update `__version__` in `src/nexiom_connect/_version.py` and add the version, with the release date, to `CHANGELOG.md`.
2. After it merges and CI passes on `main`, create and publish a GitHub Release with the tag `v` followed by the version, such as `v0.1.1`, targeting `main`.
3. The [Publish workflow](./.github/workflows/publish.yml) then:
   1. Checks out the release's commit and verifies that the stable `vX.Y.Z` tag matches `__version__`.
   2. Runs the lint, type checks, and tests, then builds the wheel and source distribution and checks them with `twine check --strict`.
   3. Waits for a maintainer to approve the `pypi` environment deployment, then publishes to PyPI with trusted publishing. PyPI records attestations of where the files were built.
   4. Attaches the wheel and source distribution to the GitHub Release.

Publishing a stable GitHub Release triggers the workflow; pushing a commit or tag alone does not. Drafts and prereleases are not published. A tag push also runs the CI job that checks the tag against `__version__`.

One-time setup, before the first release:

- On PyPI, add a trusted publisher for the project `nexiom-connect` (a pending publisher until the first upload): owner `nexiomhq`, repository `nexiom-connect-python`, workflow `publish.yml`, environment `pypi`. No API token is stored in GitHub.
- In the repository settings, create the `pypi` environment with required reviewers, so every release waits for a maintainer's approval, and restrict it to `v*` tags.
