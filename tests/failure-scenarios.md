# Failure scenarios

Every way the SDK can fail, and what it must do. Read this before changing behavior, and add a scenario before adding coverage. Each scenario names the test that covers it. Unless a row says otherwise, the sync client (`NexiomConnect`) and the async client (`AsyncNexiomConnect`) behave the same, and the tests run against both.

## Configuration

| Scenario | Expected | Test |
| --- | --- | --- |
| No `api_key` and no `NEXIOM_API_KEY` environment variable | `NexiomValidationError` naming both, before any request | `test_validation.py::test_api_key_is_required` |
| Empty API key, or a key with whitespace (including a trailing newline), control, or non-ASCII characters | `NexiomValidationError` before any request | `test_validation.py::test_invalid_configuration` |
| Base URL is empty, relative, not HTTP(S), or has credentials, a query, or a fragment | `NexiomValidationError` | `test_validation.py::test_invalid_configuration` |
| Base URL uses plain HTTP on a non-loopback host | `NexiomValidationError`; HTTP is allowed only on `localhost`, `127.0.0.1`, and `[::1]` | `test_validation.py::test_invalid_configuration` |
| Timeout is zero, negative, infinite, NaN, or a boolean; `max_retries` is outside 0–10, a float, or a boolean | `NexiomValidationError`, in the constructor and in per-request options | `test_validation.py::test_invalid_configuration`, `test_validation.py::test_invalid_request_options` |
| `http_client` of the wrong kind (an `httpx.AsyncClient` for the sync client, or the reverse) | `NexiomValidationError` | `test_validation.py::test_invalid_configuration` |
| `repr()`, `str()`, `vars()`, logging, or a traceback of the client | The API key never appears | `test_transport.py::test_api_key_is_not_exposed` |
| A caller-supplied `http_client` | Used for every request; never closed by the SDK; its redirect setting is ignored | `test_transport.py::test_custom_http_client_is_used_and_left_open` |

## Arguments

| Scenario | Expected | Test |
| --- | --- | --- |
| Unknown keyword argument, such as `fromName`, `org_id`, or `project_id` | `TypeError` from Python before any request; tenant scope can never be sent | `test_validation.py::test_unknown_keywords_are_refused` |
| Unknown key inside a mapping argument, such as `template={"templateId": ...}` | `NexiomValidationError` naming the key | `test_messaging.py::test_invalid_arguments_fail_before_any_request` |
| Empty, `.` or `..` resource ID, or an ID that is not a string | `NexiomValidationError`; other IDs are percent-encoded into one path segment | `test_validation.py::test_invalid_arguments`, `test_contacts.py::test_contact_methods` |
| `to` missing or empty, more than 100 recipients, a blank address, or `bytes` instead of `str` | `NexiomValidationError` | `test_validation.py::test_invalid_arguments` |
| CC or BCC with more than one primary recipient | `NexiomValidationError` | `test_validation.py::test_invalid_arguments` |
| No subject, or neither `html` nor `text`, without `template_id` | `NexiomValidationError` | `test_validation.py::test_invalid_arguments` |
| Idempotency key with whitespace (including a trailing newline), non-ASCII, or more than 128 characters (200 for messages) | `NexiomValidationError` | `test_validation.py::test_invalid_arguments`, `test_messaging.py::test_invalid_arguments_fail_before_any_request` |
| `scheduled_at`, `start_date`, or `end_date` that is a naive `datetime`, not an ISO 8601 timestamp (`tomorrow`), or an impossible date (`2026-02-30`) | `NexiomValidationError`; an aware `datetime` is sent in UTC, a `date` as `YYYY-MM-DD` | `test_validation.py::test_invalid_arguments`, `test_emails.py::test_dates_are_serialized` |
| `limit`, `page`, or `before_version` given as a boolean, float, or numeric string, or outside its range | `NexiomValidationError`; pages are bounded at 10,000 | `test_validation.py::test_invalid_arguments` |
| Email log cursor longer than 1,024 characters | `NexiomValidationError` | `test_validation.py::test_invalid_arguments` |
| Property type other than `string`, `number`, or `date`; blank or too-long name; fallback that is not `None` or a string of at most 1,000 characters | `NexiomValidationError` | `test_validation.py::test_invalid_arguments` |
| Property update with no field | `NexiomValidationError` | `test_validation.py::test_invalid_arguments` |
| Template `status` or `origin`, domain `status`, or contact `email_status` outside the values the API accepts | `NexiomValidationError` listing the accepted values | `test_validation.py::test_invalid_arguments` |
| Suppression `search` blank or longer than 255 characters, or `cursor` empty or longer than 400 characters | `NexiomValidationError` | `test_validation.py::test_invalid_arguments` |
| Domain create with a non-boolean `open_tracking` | `NexiomValidationError` | `test_validation.py::test_invalid_arguments` |
| `metadata`, `properties`, or `template_variables` that is not a mapping with string keys | `NexiomValidationError` | `test_validation.py::test_invalid_arguments` |
| Body that cannot be encoded as JSON (a `set`, an object, NaN, or a lone surrogate) | `NexiomValidationError` | `test_validation.py::test_invalid_arguments` |
| Empty `metadata`, `properties`, or `template_variables` | Sent as a JSON object `{}` | `test_emails.py::test_send_maps_arguments_to_the_api` |
| Optional argument left out or passed as `None` | Omitted, except `user_id` on contact update and `fallback_value`, where `None` clears the value | `test_contacts.py::test_contact_methods`, `test_contacts.py::test_property_methods` |

## API responses

| Scenario | Expected | Test |
| --- | --- | --- |
| HTTP 400, 401, 403, 404, 409, or 422 | `NexiomError` of kind `api` with status, code, request ID, and details; never retried | `test_transport.py::test_client_errors_are_not_retried` |
| HTTP 3xx redirect | `NexiomError` of kind `api`; never followed, so the API key is not forwarded | `test_transport.py::test_redirects_are_not_followed`, `test_http_server.py::test_redirect_is_not_followed` |
| HTTP error body that is not JSON | `NexiomError` keeps the HTTP status and header request ID | `test_transport.py::test_non_json_error_keeps_diagnostics` |
| 2xx body that is empty, not JSON, `null`, a string, a list, `{}`, or `{"data": null}` | `NexiomError` of kind `protocol`; never retried | `test_transport.py::test_invalid_success_bodies_are_protocol_errors` |
| Delivery detail that is not a JSON object | `NexiomError` of kind `protocol` | `test_emails.py::test_delivery_detail_must_be_an_object` |
| Property collection that is not a list of objects with a string `key` | `NexiomError` of kind `protocol` | `test_contacts.py::test_malformed_property_collections_are_protocol_errors` |
| Template variables or versions that are not a list of objects | `NexiomError` of kind `protocol` | `test_templates.py::test_malformed_lists_are_protocol_errors` |
| `NexiomError` pickled and unpickled (Celery, multiprocessing) | Keeps its message, kind, status, code, request ID, details, and response metadata | `test_transport.py::test_errors_survive_pickling` |

## Retries and deadlines

| Scenario | Expected | Test |
| --- | --- | --- |
| HTTP 408, 429, 500, 502, 503, or 504 on an email send | Retried with the same idempotency key and body | `test_transport.py::test_email_send_retries_with_the_same_key` |
| Same statuses on reads, cancels, and domain verification | Retried up to `max_retries` | `test_transport.py::test_reads_retry_a_bounded_number_of_times`, `test_emails.py::test_cancel_and_delivery_reads_retry`, `test_domains.py::test_verify_retries` |
| Same statuses on contact or property mutations, reschedules, and domain creation or deletion | Never retried, whatever `max_retries` is | `test_transport.py::test_mutations_never_retry` |
| Network failure | `NexiomError` of kind `network`; neither `__cause__` nor `__context__` holds the transport exception, so the request and its `Authorization` header cannot leak | `test_transport.py::test_network_failure_is_redacted` |
| Network failure after a retried HTTP error | Response metadata from the earlier attempt is cleared | `test_transport.py::test_network_failure_clears_stale_metadata` |
| `Retry-After` (seconds or HTTP date) that ends after the deadline | The API error is raised at once instead of waiting into a timeout | `test_transport.py::test_retry_after_beyond_the_deadline_fails_fast` |
| `Retry-After` within the deadline | Honored | `test_transport.py::test_retry_after_within_the_deadline_is_honored` |
| Server does not answer before the deadline, or sends its body too slowly | `NexiomError` of kind `timeout`; the deadline covers every attempt, wait, and body read | `test_http_server.py::test_slow_server_times_out`, `test_http_server.py::test_slow_body_times_out` |
| Request times out after the SDK generated an idempotency key | The key is on `error.response.idempotency_key`, so the caller can retry safely | `test_http_server.py::test_slow_server_times_out` |
| Per-request `timeout` or `max_retries` | Overrides the client default for that call only | `test_transport.py::test_per_request_overrides` |
| Async request cancelled by the caller (`asyncio.wait_for`, a task group, trio cancel scope) | The cancellation propagates unchanged; it is never turned into a `NexiomError` or retried | `test_transport.py::test_async_cancellation_propagates` |
| Async client under trio instead of asyncio | Works the same; retry waits use anyio | `test_transport.py::test_async_client_runs_on_trio` |

## Messaging

| Scenario | Expected | Test |
| --- | --- | --- |
| `channel` missing, or a channel not available yet such as `sms` | `NexiomValidationError` listing the channels, before any request | `test_messaging.py::test_invalid_arguments_fail_before_any_request` |
| `from_` or `to` missing, or not an E.164 number (a local number, a sender ID such as `was_1`) | `NexiomValidationError` before any request | `test_messaging.py::test_invalid_arguments_fail_before_any_request` |
| `template` missing or without an `id`; a template key other than `id` or `variables`; a variables key other than `header` or `body` | `NexiomValidationError` naming the key | `test_messaging.py::test_invalid_arguments_fail_before_any_request` |
| Variables given as a list, a key that is not a variable number or name (including one with a trailing newline), a boolean key, or a value that is not a string or is longer than 1,024 characters | `NexiomValidationError` | `test_messaging.py::test_invalid_arguments_fail_before_any_request` |
| Numbered variables written as integer keys (`{1: "Amina"}`) | Sent as a JSON object `{"1": "Amina"}`; an empty map is sent as `{}` | `test_messaging.py::test_send_posts_the_template_with_an_idempotency_key` |
| HTTP 408, 429, 500, 502, 503, or 504 on a send | Retried with the same idempotency key and body | `test_messaging.py::test_sends_and_reads_retry_transient_failures` |
| HTTP 409 or 422 on a send, such as `whatsapp_template_not_approved` | `NexiomError` with the status and code; never retried | `test_messaging.py::test_api_refusals_are_not_retried` |
| A send or message read whose `data` is not a message of a known channel | `NexiomError` of kind `protocol` | `test_messaging.py::test_malformed_messages_are_protocol_errors` |

## Webhook verification

| Scenario | Expected | Test |
| --- | --- | --- |
| `x-nexiom-timestamp` or `x-nexiom-signature` missing or blank | `NexiomWebhookVerificationError` with reason `missing_headers` | `test_webhooks.py::test_missing_or_malformed_headers_are_refused` |
| Timestamp that is not whole Unix seconds, or too large to compare | Reason `invalid_timestamp` | `test_webhooks.py::test_missing_or_malformed_headers_are_refused` |
| Timestamp more than the tolerance (default 300 seconds) before or after now | Reason `timestamp_out_of_tolerance`; a custom `tolerance` widens or narrows it | `test_webhooks.py::test_timestamps_outside_the_tolerance_are_refused` |
| Body, timestamp, secret, or signature changed, including re-encoded JSON or a secret without its `whsec_` prefix | Reason `invalid_signature`; the comparison takes constant time | `test_webhooks.py::test_changed_requests_are_refused` |
| Correctly signed body that is not JSON, not UTF-8, or not an envelope with `id`, `type`, integer `schema_version`, object `data`, and `created_at` | Reason `invalid_payload` | `test_webhooks.py::test_signed_bodies_that_are_not_events_are_refused` |
| Body given as `str`, `bytes`, `bytearray`, or `memoryview` | Verified over the same bytes | `test_webhooks.py::test_signed_requests_return_their_event` |
| Headers from Django, Flask, or Starlette (case-insensitive mappings), a plain `dict` in any letter case, a list of pairs, list values, or `bytes` values | Read case-insensitively; the first value is used | `test_webhooks.py::test_headers_are_read_from_every_framework_shape` |
| Empty secret, a tolerance below 1 or a boolean, or a payload that is not text or bytes | `NexiomValidationError`, not a verification failure | `test_webhooks.py::test_invalid_arguments_are_programming_errors` |
| Event type the SDK does not know yet | Verified and returned | `test_webhooks.py::test_signed_requests_return_their_event` |
| Verification without an API key | `Webhooks().construct_event(...)` works without creating a client | `test_webhooks.py::test_webhooks_work_without_a_client` |

## Packaging

| Scenario | Expected | Test |
| --- | --- | --- |
| Installed from the built wheel into a clean environment | Imports, exposes `__version__`, ships `py.typed`, and has no test or example files | CI `package` job |
| Release tag differs from `nexiom_connect.__version__`, or is not a stable `vX.Y.Z` | The publish workflow fails before building | `publish.yml` "Verify release version" |
| A consumer type-checks code that uses the SDK | `mypy --strict` passes over `tests/typecheck/consumer.py`, including narrowing webhook events by `type` | `tests/typecheck/consumer.py` |
