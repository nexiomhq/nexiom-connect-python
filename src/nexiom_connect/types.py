"""Typed shapes of the API's parameters, responses, and webhook events.

Responses keep the API's field names, including snake_case and camelCase fields, and dates stay
ISO 8601 strings. These are `TypedDict`s: at runtime every response is a plain `dict`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal, TypeAlias, TypedDict

__all__ = [
    "CancelEmailResponse",
    "Contact",
    "ContactActivity",
    "ContactDetails",
    "ContactEmailStatus",
    "ContactEvent",
    "ContactEventData",
    "ContactEventType",
    "ContactListItem",
    "ContactProperty",
    "ContactPropertyType",
    "ContactPropertyValue",
    "DeleteResponse",
    "DnsRecordStatus",
    "Domain",
    "DomainDnsRecord",
    "DomainStatus",
    "Email",
    "EmailDeliveryReason",
    "EmailEvent",
    "EmailEventData",
    "EmailEventType",
    "EmailListItem",
    "EmailScheduledEvent",
    "EmailScheduledEventData",
    "EmailSource",
    "EmailStatus",
    "EmailSuppression",
    "EmailSuppressionReason",
    "ListContactsResponse",
    "ListDomainsResponse",
    "ListEmailSuppressionsResponse",
    "ListEmailsResponse",
    "ListTemplatesResponse",
    "Message",
    "MessageChannel",
    "MessageDetails",
    "RescheduleEmailResponse",
    "SendEmailResponse",
    "Template",
    "TemplateListStatus",
    "TemplateOrigin",
    "TemplateVariable",
    "TemplateVariableType",
    "TemplateVersion",
    "TemplateVersionStatus",
    "WebhookEvent",
    "WebhookEventType",
    "WhatsAppChat",
    "WhatsAppContentSegment",
    "WhatsAppMedia",
    "WhatsAppMessage",
    "WhatsAppMessageContent",
    "WhatsAppMessageDetails",
    "WhatsAppMessageDirection",
    "WhatsAppMessageEvent",
    "WhatsAppMessageEventData",
    "WhatsAppMessageFailedEvent",
    "WhatsAppMessageFailedEventData",
    "WhatsAppMessageReceivedEvent",
    "WhatsAppMessageStatus",
    "WhatsAppMessageType",
    "WhatsAppReceivedMessage",
    "WhatsAppTemplate",
    "WhatsAppTemplateCategory",
    "WhatsAppTemplateVariables",
]


class DeleteResponse(TypedDict):
    success: bool


# Emails

EmailStatus: TypeAlias = Literal[
    "scheduled",
    "canceled",
    "queued",
    "sending",
    "accepted",
    "delivered",
    "bounced",
    "complained",
    "failed",
    "suppressed",
]

EmailSource: TypeAlias = Literal["api", "smtp", "broadcast"]

EmailDeliveryReason: TypeAlias = Literal[
    "unsubscribed",
    "complaint",
    "hard_bounce",
    "invalid",
    "manual",
    "recipient_blocked",
    "envelope_recipient_blocked",
    "temporary_failure",
    "sending_paused",
    "review_required",
    "review_expired",
    "sending_delayed",
    "delivery_uncertain",
    "message_blocked",
    "sending_failed",
    "quota_exceeded",
    "canceled",
]


class SendEmailResponse(TypedDict):
    """Acceptance means queued or scheduled, not delivered."""

    totalQueued: int
    messageId: str
    deliveryIds: list[str]

    scheduledAt: str | None
    """The scheduled send time, or `None` for an immediate send."""


class CancelEmailResponse(TypedDict):
    messageId: str
    status: Literal["canceled"]
    canceledAt: str
    deliveryIds: list[str]


class RescheduleEmailResponse(TypedDict):
    messageId: str
    status: Literal["scheduled"]
    scheduledAt: str
    deliveryIds: list[str]


class EmailListItem(TypedDict):
    """One recipient delivery."""

    id: str
    created_at: str
    recipient: str
    subject: str
    status: EmailStatus
    scheduled_at: str | None


class ListEmailsResponse(TypedDict):
    items: list[EmailListItem]

    total: int | None
    """`None` when the API does not count the matching deliveries."""

    limit: int
    hasMore: bool
    nextCursor: str | None


class _EmailDomain(TypedDict):
    id: str
    domain: str


class _EmailContact(TypedDict):
    id: str
    email: str
    first_name: str | None
    last_name: str | None


class _EmailTemplate(TypedDict):
    id: str
    name: str


class Email(TypedDict):
    """One recipient delivery with its content and history."""

    id: str
    created_at: str
    recipient: str
    subject: str
    status: EmailStatus
    scheduled_at: str | None
    message_id: str
    recipient_name: str | None
    from_address: str
    from_name: str | None
    sending_domain: str | None
    source: EmailSource
    delivery_reason: EmailDeliveryReason | None
    status_message: str | None
    canceled_at: str | None
    html_content: str | None
    text_content: str | None
    accepted_at: str | None
    delivered_at: str | None
    bounced_at: str | None
    complained_at: str | None
    failed_at: str | None
    bounce_type: str | None
    first_opened_at: str | None
    first_clicked_at: str | None
    open_count: int
    click_count: int
    domain: _EmailDomain | None
    contact: _EmailContact | None
    template: _EmailTemplate | None


EmailSuppressionReason: TypeAlias = Literal[
    "hard_bounce",
    "complaint",
    "unsubscribed",
    "invalid",
    "manual",
    "temporary_failure",
]


class EmailSuppression(TypedDict):
    email: str

    reason: EmailSuppressionReason
    """When an address has several reasons, the one that applies to your sends."""


class ListEmailSuppressionsResponse(TypedDict):
    items: list[EmailSuppression]
    nextCursor: str | None
    hasMore: bool


# Contacts

ContactEmailStatus: TypeAlias = Literal["subscribed", "unsubscribed"]

ContactPropertyValue: TypeAlias = str | int | float | None


class ContactListItem(TypedDict):
    id: str
    email: str
    first_name: str | None
    last_name: str | None
    phone_number: str | None
    email_status: ContactEmailStatus
    created_at: str


class Contact(TypedDict):
    id: str
    email: str
    first_name: str | None
    last_name: str | None
    phone_number: str | None
    email_status: ContactEmailStatus
    created_at: str
    user_id: str | None
    updated_at: str
    deleted_at: str | None
    source: str | None
    last_emailed_at: str | None
    last_opened_at: str | None
    last_clicked_at: str | None
    total_emails_sent: int
    total_emails_opened: int
    total_emails_clicked: int


class ContactActivity(TypedDict):
    id: str
    created_at: str
    updated_at: str
    deleted_at: str | None
    type: str
    description: str | None
    metadata: dict[str, Any] | None
    occurred_at: str
    channel: str | None
    resource_type: str | None
    resource_id: str | None


class ContactDetails(TypedDict):
    """A contact with its properties and activity."""

    id: str
    email: str
    first_name: str | None
    last_name: str | None
    phone_number: str | None
    email_status: ContactEmailStatus
    created_at: str
    user_id: str | None
    updated_at: str
    deleted_at: str | None
    source: str | None
    last_emailed_at: str | None
    last_opened_at: str | None
    last_clicked_at: str | None
    total_emails_sent: int
    total_emails_opened: int
    total_emails_clicked: int
    organization: str
    properties: dict[str, ContactPropertyValue] | None
    email_delivery_block_reason: str | None
    unsubscribed: bool
    activities: list[ContactActivity]


class ListContactsResponse(TypedDict):
    items: list[ContactListItem]
    total: int
    page: int
    limit: int


ContactPropertyType: TypeAlias = Literal["string", "number", "date"]


class ContactProperty(TypedDict):
    id: str
    key: str
    type: ContactPropertyType
    fallback_value: str | None
    created_at: str
    updated_at: str
    deleted_at: str | None


# Templates

TemplateListStatus: TypeAlias = Literal["draft", "published", "changes_in_draft", "archived"]
"""`changes_in_draft` means a published template with an unpublished draft."""

TemplateOrigin: TypeAlias = Literal["custom", "prebuilt"]

TemplateVersionStatus: TypeAlias = Literal["draft", "published", "saved"]
"""`draft` is being edited, `published` is used by sends, and `saved` is an earlier version."""

TemplateVariableType: TypeAlias = Literal["string", "number"]


class TemplateVariable(TypedDict):
    id: str
    key: str
    type: TemplateVariableType
    required: bool
    fallback_value: str | int | float | None


class TemplateVersion(TypedDict):
    id: str
    template_id: str
    version_number: int
    status: TemplateVersionStatus
    subject: str
    preview_text: str | None
    from_name: str | None
    from_address: str | None
    reply_to: str | None

    content: dict[str, Any]
    """The dashboard editor's document; build on `html` and `text` instead."""

    html: str
    text: str | None
    thumbnail_url: str | None
    editor_revision: int
    created_by_customer_id: str | None
    published_by_customer_id: str | None
    published_at: str | None
    created_at: str
    updated_at: str
    variables: list[TemplateVariable]


class Template(TypedDict):
    id: str
    organization_id: str
    project_id: str
    name: str
    alias: str
    description: str | None
    category: str | None
    origin: TemplateOrigin
    locale: str
    draft_version_id: str | None
    published_version_id: str | None
    archived_at: str | None
    usage_count: int
    last_used_at: str | None
    created_at: str
    updated_at: str
    draft_version: TemplateVersion | None

    published_version: TemplateVersion | None
    """The version sends use; its variables are exactly what a send needs."""


class ListTemplatesResponse(TypedDict):
    items: list[Template]
    total: int
    page: int
    limit: int


# Sending domains

DomainStatus: TypeAlias = Literal["pending", "verified", "failed"]

DnsRecordStatus: TypeAlias = Literal[
    "not_started", "pending", "verified", "failed", "temporary_failure"
]


class DomainDnsRecord(TypedDict):
    id: str
    purpose: str
    record_type: str
    name: str
    value: str
    priority: int | None
    status: DnsRecordStatus
    required_for_sending: bool
    last_checked_at: str | None
    error_code: str | None
    error_message: str | None


class _DomainFields(TypedDict):
    id: str
    domain: str
    status: DomainStatus
    region: str
    open_tracking: bool

    verification_error: str | None
    """What still needs attention when the domain is not verified."""

    verification_attempts: int
    verification_attempted_at: str | None
    last_verified_at: str | None
    created_at: str
    updated_at: str


class Domain(_DomainFields, total=False):
    dns_records: list[DomainDnsRecord]
    """The DNS records to publish, when the API includes them."""


class ListDomainsResponse(TypedDict):
    items: list[Domain]
    total: int
    page: int
    limit: int


# Messaging

MessageChannel: TypeAlias = Literal["whatsapp"]
"""Messaging channels. New channels are added here."""

WhatsAppTemplateVariables: TypeAlias = Mapping[str | int, str]
"""Values for a template's variables, keyed by variable number (`1` or `"1"`) or name."""


class _WhatsAppTemplateVariableGroups(TypedDict, total=False):
    header: WhatsAppTemplateVariables | None
    body: WhatsAppTemplateVariables | None


class _WhatsAppTemplateId(TypedDict):
    id: str
    """The template's ID (`mtp_…`), or its approval's ID (`wat_…`)."""


class WhatsAppTemplate(_WhatsAppTemplateId, total=False):
    """An approved WhatsApp template and the values of its variables."""

    variables: _WhatsAppTemplateVariableGroups | None
    """Every header and body variable of the template; leave it out for a template without variables."""


WhatsAppMessageDirection: TypeAlias = Literal["outbound", "inbound"]

WhatsAppMessageType: TypeAlias = Literal[
    "template",
    "text",
    "image",
    "video",
    "audio",
    "document",
    "sticker",
    "location",
    "contacts",
    "interactive",
    "button",
    "reaction",
    "unsupported",
]

WhatsAppMessageStatus: TypeAlias = Literal[
    "sending",
    "accepted",
    "sent",
    "delivered",
    "read",
    "failed",
    "uncertain",
    "received",
]
"""`accepted` means WhatsApp accepted the message, not that it was delivered. `uncertain` means
WhatsApp did not confirm it; it is never resent automatically. Received messages are `received`."""

WhatsAppTemplateCategory: TypeAlias = Literal["marketing", "utility", "authentication"]


class _WhatsAppTemplateReference(TypedDict):
    id: str
    name: str
    language: str
    version: int


class WhatsAppMessage(TypedDict):
    """A message as returned by a send."""

    id: str
    """Message ID (`msg_…`)."""

    channel: Literal["whatsapp"]
    direction: WhatsAppMessageDirection
    type: WhatsAppMessageType
    status: WhatsAppMessageStatus

    sender: str
    """Who sent the message: your number for a message you sent, the customer for a received one."""

    sender_name: str | None
    recipient: str
    category: WhatsAppTemplateCategory | None
    template: _WhatsAppTemplateReference | None

    is_billable: bool
    """Counts toward the plan's included messages, or is paid from the wallet beyond them."""

    cost: str
    """What Nexiom Connect charged, as a decimal string such as `"0.1000"`. Excludes Meta's fees."""

    cost_currency: str
    """ISO 4217 currency of `cost`."""

    failure_code: str | None
    """For a failed message: `meta_` and WhatsApp's error code, or `meta_error`."""

    failure_reason: str | None
    created_at: str
    accepted_at: str | None
    sent_at: str | None
    delivered_at: str | None
    read_at: str | None
    failed_at: str | None
    reply_to: str | None
    contact_name: str | None
    preview: str | None


class WhatsAppContentSegment(TypedDict):
    """Template text (`variable` is `None`), or a variable with the value it was sent with."""

    text: str | None
    variable: str | None


class _WhatsAppCarouselCard(TypedDict):
    body: list[WhatsAppContentSegment]
    buttons: list[str]
    button_values: dict[str, str]


class WhatsAppMessageContent(TypedDict):
    header: list[WhatsAppContentSegment] | None
    body: list[WhatsAppContentSegment] | None
    footer: str | None

    buttons: list[str]
    """Button labels, in order."""

    button_values: dict[str, str]
    cards: list[_WhatsAppCarouselCard]


class WhatsAppChat(TypedDict):
    contact_name: str | None
    contact_phone: str | None
    service_window_expires_at: str | None
    free_entry_expires_at: str | None
    can_send_free_form: bool


class WhatsAppMedia(TypedDict):
    status: Literal["pending", "ready", "unavailable"]
    file_id: str | None
    mime_type: str | None
    size_bytes: int | None
    filename: str | None
    caption: str | None
    link: str | None


class _WhatsAppMessageDetailsFields(TypedDict):
    id: str
    channel: Literal["whatsapp"]
    direction: WhatsAppMessageDirection
    type: WhatsAppMessageType
    status: WhatsAppMessageStatus
    sender: str
    sender_name: str | None
    recipient: str
    category: WhatsAppTemplateCategory | None
    template: _WhatsAppTemplateReference | None
    is_billable: bool
    cost: str
    cost_currency: str
    failure_code: str | None
    failure_reason: str | None
    created_at: str
    accepted_at: str | None
    sent_at: str | None
    delivered_at: str | None
    read_at: str | None
    failed_at: str | None
    reply_to: str | None
    contact_name: str | None
    preview: str | None

    content: WhatsAppMessageContent | None
    """For a template, the message as the recipient received it."""

    chat: WhatsAppChat | None


class WhatsAppMessageDetails(_WhatsAppMessageDetailsFields, total=False):
    """A message with what it said. The content of other types is in the field named by `type`."""

    text: dict[str, Any]
    image: WhatsAppMedia
    video: WhatsAppMedia
    audio: WhatsAppMedia
    document: WhatsAppMedia
    sticker: WhatsAppMedia
    header_media: dict[str, Any]
    location: dict[str, Any]
    contacts: list[dict[str, Any]]
    interactive: dict[str, Any]
    button: dict[str, Any]
    reaction: dict[str, Any]
    unsupported: dict[str, Any]
    referral: dict[str, Any]


Message: TypeAlias = WhatsAppMessage
"""A message on any channel; check `channel` to read its channel's fields."""

MessageDetails: TypeAlias = WhatsAppMessageDetails
"""A message with its content, on any channel."""


# Webhook events

EmailEventType: TypeAlias = Literal[
    "email.scheduled",
    "email.canceled",
    "email.sent",
    "email.delivered",
    "email.delivery_delayed",
    "email.bounced",
    "email.complained",
    "email.failed",
    "email.opened",
    "email.clicked",
]

ContactEventType: TypeAlias = Literal[
    "contact.created",
    "contact.updated",
    "contact.deleted",
    "contact.unsubscribed",
]

WhatsAppEventType: TypeAlias = Literal[
    "whatsapp.message.sent",
    "whatsapp.message.delivered",
    "whatsapp.message.read",
    "whatsapp.message.failed",
    "whatsapp.message.received",
]

WebhookEventType: TypeAlias = EmailEventType | ContactEventType | WhatsAppEventType


class EmailEventData(TypedDict):
    id: str
    """Recipient delivery ID."""

    message_id: str
    """Message ID shared by the deliveries of one send."""

    recipient: str
    occurred_at: str


class EmailScheduledEventData(TypedDict):
    id: str
    message_id: str
    recipient: str
    occurred_at: str

    scheduled_at: str
    """The current send time of the delivery."""


class ContactEventData(TypedDict):
    id: str
    email: str | None
    status: ContactEmailStatus
    first_name: str | None
    last_name: str | None


class _WhatsAppEventTemplate(TypedDict):
    id: str
    name: str
    language: str


class WhatsAppMessageEventData(TypedDict):
    id: str
    """Message ID (`msg_…`), as returned by `messaging.send`."""

    sender: str
    recipient: str
    template: _WhatsAppEventTemplate | None

    occurred_at: str
    """The time WhatsApp reported for this status."""


class WhatsAppMessageFailedEventData(TypedDict):
    id: str
    sender: str
    recipient: str
    template: _WhatsAppEventTemplate | None
    occurred_at: str

    failure_code: str
    """`meta_` and WhatsApp's error code, such as `meta_131026`, or `meta_error`."""

    failure_reason: str | None


class _WhatsAppProfile(TypedDict):
    name: str | None


class _WhatsAppReceivedMessageFields(TypedDict):
    id: str
    sender: str
    recipient: str
    type: WhatsAppMessageType
    reply_to: str | None
    contact: _WhatsAppProfile
    occurred_at: str


class WhatsAppReceivedMessage(_WhatsAppReceivedMessageFields, total=False):
    """A message a customer sent. Its content is in the field named by `type`."""

    text: dict[str, Any]
    image: WhatsAppMedia
    video: WhatsAppMedia
    audio: WhatsAppMedia
    document: WhatsAppMedia
    sticker: WhatsAppMedia
    location: dict[str, Any]
    contacts: list[dict[str, Any]]
    interactive: dict[str, Any]
    button: dict[str, Any]
    reaction: dict[str, Any]
    unsupported: dict[str, Any]
    referral: dict[str, Any]


class EmailEvent(TypedDict):
    id: str
    """Event ID. Retries and replays carry the same ID: deduplicate on it."""

    type: Literal[
        "email.canceled",
        "email.sent",
        "email.delivered",
        "email.delivery_delayed",
        "email.bounced",
        "email.complained",
        "email.failed",
        "email.opened",
        "email.clicked",
    ]
    schema_version: int
    data: EmailEventData
    created_at: str


class EmailScheduledEvent(TypedDict):
    id: str
    type: Literal["email.scheduled"]
    schema_version: int
    data: EmailScheduledEventData
    created_at: str


class ContactEvent(TypedDict):
    id: str
    type: ContactEventType
    schema_version: int
    data: ContactEventData
    created_at: str


class WhatsAppMessageEvent(TypedDict):
    id: str
    type: Literal["whatsapp.message.sent", "whatsapp.message.delivered", "whatsapp.message.read"]
    schema_version: int
    data: WhatsAppMessageEventData
    created_at: str


class WhatsAppMessageFailedEvent(TypedDict):
    id: str
    type: Literal["whatsapp.message.failed"]
    schema_version: int
    data: WhatsAppMessageFailedEventData
    created_at: str


class WhatsAppMessageReceivedEvent(TypedDict):
    id: str
    type: Literal["whatsapp.message.received"]
    schema_version: int
    data: WhatsAppReceivedMessage
    created_at: str


WebhookEvent: TypeAlias = (
    EmailEvent
    | EmailScheduledEvent
    | ContactEvent
    | WhatsAppMessageEvent
    | WhatsAppMessageFailedEvent
    | WhatsAppMessageReceivedEvent
)
"""A verified webhook event. Checking `type` narrows `data`.

Event types added after this SDK version are still verified and returned at runtime: handle them
in a default branch.
"""
