"""
Example Email Notification Plugin
Demonstrates custom notification channels.
"""

from typing import Any

from src.plugin_system import NotificationPlugin, PluginMetadata


class EmailNotifier(NotificationPlugin):
    """Send notifications via email (example implementation)."""

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="Email Notifier",
            version="1.0.0",
            description="Sends notifications via email (SMTP)",
            author="Scalers Team",
            dependencies=["smtplib"],
        )

    def get_channel_name(self) -> str:
        return "email"

    def send_notification(self, message: str, metadata: dict[str, Any] | None = None) -> bool:
        """
        Send email notification.

        Note: This is an example implementation. In production, you would:
        1. Configure SMTP settings from environment/config
        2. Use proper email templates
        3. Handle attachments and HTML formatting
        4. Add retry logic for failures
        """
        import logging

        logger = logging.getLogger(__name__)

        # Example: Extract email-specific metadata
        recipient = metadata.get("recipient", "admin@example.com") if metadata else "admin@example.com"
        subject = metadata.get("subject", "Scalers Slack Notification") if metadata else "Notification"

        # In a real implementation, you would send via SMTP here
        # For this example, we just log it
        logger.info(
            "📧 Email notification (not actually sent - example only):\n  To: %s\n  Subject: %s\n  Message: %s",
            recipient,
            subject,
            message[:100],
        )

        # Simulated success
        return True


class SMSNotifier(NotificationPlugin):
    """Send notifications via SMS (example implementation)."""

    def get_metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="SMS Notifier",
            version="1.0.0",
            description="Sends notifications via SMS using Twilio",
            author="Scalers Team",
            dependencies=["twilio"],
            enabled=False,  # Disabled by default
        )

    def get_channel_name(self) -> str:
        return "sms"

    def send_notification(self, message: str, metadata: dict[str, Any] | None = None) -> bool:
        """Send SMS notification (example stub)."""
        import logging

        logger = logging.getLogger(__name__)

        phone = metadata.get("phone", "+1234567890") if metadata else "+1234567890"

        logger.info("📱 SMS notification (stub): %s -> %s", message[:50], phone)

        return True
