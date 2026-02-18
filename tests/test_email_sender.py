"""Tests for email_sender utility functions."""

from utils.email_sender import send_email_with_attachment, send_email_with_attachment_bytes


def test_send_email_requires_credentials():
    """Should return False when sender credentials are empty."""
    result = send_email_with_attachment(
        to_email="test@example.com",
        subject="Test",
        body="Test body",
        attachment_path="/nonexistent/file.pptx",
        sender_email="",
        sender_password="",
    )
    assert result is False


def test_send_email_bytes_requires_credentials():
    """Should return False when sender credentials are empty."""
    result = send_email_with_attachment_bytes(
        to_email="test@example.com",
        subject="Test",
        body="Test body",
        attachment_bytes=b"fake pptx data",
        filename="test.pptx",
        sender_email="",
        sender_password="",
    )
    assert result is False
