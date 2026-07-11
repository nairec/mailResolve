from src.classifier.features import EmailFeatures, _has_attachment, _headers_map, _parse_from_address


def test_parse_from_address_with_display_name() -> None:
    email, domain = _parse_from_address("GitHub <notifications@github.com>")
    assert email == "notifications@github.com"
    assert domain == "github.com"


def test_headers_map_normalizes_names() -> None:
    headers = _headers_map(
        {
            "headers": [
                {"name": "List-Unsubscribe", "value": "<mailto:unsub@example.com>"},
                {"name": "Subject", "value": "Hello"},
            ]
        }
    )
    assert headers["list-unsubscribe"] == "<mailto:unsub@example.com>"
    assert headers["subject"] == "Hello"


def test_has_attachment_detects_nested_part() -> None:
    payload = {
        "parts": [
            {"mimeType": "text/plain"},
            {"filename": "invoice.pdf", "mimeType": "application/pdf"},
        ]
    }
    assert _has_attachment(payload) is True


def test_email_features_from_parsed_values() -> None:
    features = EmailFeatures(
        message_id="msg-1",
        from_email="noreply@github.com",
        from_domain="github.com",
        to="me@example.com",
        subject="CI failed",
        snippet="Build failed on main",
        label_ids=("INBOX", "UNREAD"),
        is_unread=True,
        has_attachment=False,
        internal_date=None,
        list_unsubscribe=None,
        precedence=None,
        x_mailer=None,
        auto_submitted="auto-generated",
    )
    assert features.is_unread is True
    assert features.from_domain == "github.com"
