"""
WhatsApp Channel Handler (Twilio)

Handles incoming WhatsApp messages via Twilio webhooks
and sends replies via Twilio WhatsApp API.

Prerequisites:
- Twilio account with WhatsApp Sandbox or Business API
- Twilio Account SID, Auth Token, and WhatsApp number
- Webhook endpoint configured to this handler
"""

import os
import logging
from typing import Dict, Any, Optional, List

from twilio.rest import Client
from twilio.request_validator import RequestValidator
from fastapi import Request, HTTPException, Response
import asyncio

logger = logging.getLogger(__name__)


class WhatsAppHandler:
    """Handler for WhatsApp integration via Twilio."""

    def __init__(self):
        """Initialize Twilio client from environment variables."""
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.whatsapp_number = os.getenv('TWILIO_WHATSAPP_NUMBER')  # e.g., 'whatsapp:+14155238886'

        if not all([self.account_sid, self.auth_token, self.whatsapp_number]):
            raise ValueError(
                "Twilio configuration missing. Set TWILIO_ACCOUNT_SID, "
                "TWILIO_AUTH_TOKEN, and TWILIO_WHATSAPP_NUMBER environment variables."
            )

        self.client = Client(self.account_sid, self.auth_token)
        self.validator = RequestValidator(self.auth_token)
        logger.info("WhatsApp handler initialized")

    async def validate_webhook(self, request: Request) -> bool:
        """
        Validate incoming Twilio webhook signature.

        Args:
            request: FastAPI Request object

        Returns:
            True if signature valid
        Raises:
            HTTPException 403 if invalid
        """
        try:
            signature = request.headers.get('X-Twilio-Signature', '')
            url = str(request.url)
            form_data = await request.form()
            params = dict(form_data)

            is_valid = self.validator.validate(url, params, signature)
            if not is_valid:
                logger.warning(f"Invalid Twilio webhook signature for URL: {url}")
                return False

            return True
        except Exception as e:
            logger.error(f"Webhook validation error: {e}")
            return False

    async def process_webhook(self, form_data: Dict[str, str]) -> Dict[str, Any]:
        """
        Process incoming WhatsApp message from Twilio webhook.

        Args:
            form_data: Twilio webhook form data

        Returns:
            Normalized message dictionary ready for Kafka ingestion
        """
        # Extract message data
        message_sid = form_data.get('MessageSid')
        from_number = form_data.get('From', '').replace('whatsapp:', '')
        body = form_data.get('Body', '')
        num_media = int(form_data.get('NumMedia', '0'))
        profile_name = form_data.get('ProfileName', '')
        status = form_data.get('SmsStatus', '')

        # Handle media if present
        media_urls = []
        for i in range(num_media):
            media_url = form_data.get(f'MediaUrl{i}')
            if media_url:
                media_urls.append({
                    'url': media_url,
                    'content_type': form_data.get(f'MediaContentType{i}')
                })

        return {
            'channel': 'whatsapp',
            'channel_message_id': message_sid,
            'customer_phone': from_number,
            'customer_name': profile_name,
            'content': body,
            'received_at': datetime.utcnow().isoformat() + 'Z',
            'metadata': {
                'num_media': num_media,
                'media_urls': media_urls,
                'status': status,
                'wa_id': form_data.get('WaId'),
                'profile_name': profile_name
            }
        }

    async def send_message(
        self,
        to_phone: str,
        body: str,
        max_parts: int = 1
    ) -> Dict[str, Any]:
        """
        Send WhatsApp message via Twilio.

        Args:
            to_phone: Phone number in E.164 format (e.g., +15551234567)
            body: Message text (max 1600 chars per message)
            max_parts: Maximum number of message parts to send (safety limit)

        Returns:
            Dict with message SID and delivery status
        """
        # Ensure phone number has whatsapp: prefix
        if not to_phone.startswith('whatsapp:'):
            to_phone = f'whatsapp:{to_phone}'

        # WhatsApp message limit is 1600 chars but optimal is < 300
        if len(body) > 1600:
            logger.warning(f"WhatsApp message too long ({len(body)} chars). Truncating.")
            body = body[:1597] + "..."

        try:
            message = self.client.messages.create(
                body=body,
                from_=self.whatsapp_number,
                to=to_phone
            )

            logger.info(f"Sent WhatsApp message to {to_phone} (SID: {message.sid})")

            return {
                'channel_message_id': message.sid,
                'delivery_status': message.status,  # 'queued', 'sent', 'delivered', 'failed', 'read'
                'to': to_phone,
                'num_segments': message.num_segments
            }

        except Exception as e:
            logger.error(f"Failed to send WhatsApp message to {to_phone}: {e}")
            return {
                'channel_message_id': None,
                'delivery_status': 'failed',
                'error': str(e)
            }

    def format_response(self, response: str, max_length: int = 300) -> List[str]:
        """
        Format and split response for WhatsApp.

        WhatsApp best practices:
        - Optimal length: 1-2 sentences (<160 chars)
        - Send multiple messages if needed using send_message multiple times
        - Break at sentence boundaries for readability

        Args:
            response: Full response text
            max_length: Maximum message length per part (default 300 for UX)

        Returns:
            List of message parts ready to send
        """
        if len(response) <= max_length:
            return [response]

        # Split at sentence boundaries
        sentences = response.replace('!', '.').replace('?', '.').split('.')
        messages = []
        current_msg = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # If adding this sentence would exceed limit, commit current message
            if len(current_msg) + len(sentence) + 2 > max_length and current_msg:
                messages.append(current_msg.rstrip())
                current_msg = sentence + ". "
            else:
                current_msg += sentence + ". "

        if current_msg.strip():
            messages.append(current_msg.rstrip())

        # Safety: ensure we have at least one message and each is within limit
        if not messages:
            messages = [response[:max_length]]
        else:
            for i, msg in enumerate(messages):
                if len(msg) > max_length:
                    messages[i] = msg[:max_length - 3] + "..."

        return messages[:3]  # Safety: max 3 message parts

    async def mark_as_read(self, message_sid: str):
        """Mark WhatsApp message as read via Twilio API."""
        try:
            # Twilio doesn't have explicit mark_as_read for WhatsApp,
            # but we can update message status if needed
            logger.debug(f"Marking message {message_sid} as read")
        except Exception as e:
            logger.warning(f"Failed to mark message {message_sid} as read: {e}")


# Webhook endpoint helper (used in FastAPI)
async def handle_whatsapp_webhook(form_data: Dict[str, str], handler: 'WhatsAppHandler') -> Response:
    """
    Process WhatsApp webhook and return TwiML response.

    This is called from FastAPI webhook endpoint after signature validation.

    Args:
        form_data: Twilio form webhook data
        handler: Initialized WhatsAppHandler instance

    Returns:
        FastAPI Response with TwiML XML (empty response for async processing)
    """
    try:
        message_data = await handler.process_webhook(form_data)

        # Publish to Kafka for async processing (happens elsewhere)
        # Here we just acknowledge receipt
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
            media_type="application/xml"
        )
    except Exception as e:
        logger.error(f"WhatsApp webhook error: {e}", exc_info=True)
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
            media_type="application/xml"
        )


# Status callback handler (for delivery receipts)
async def handle_status_callback(form_data: Dict[str, str]):
    """
    Handle WhatsApp message status updates (delivered, read, failed).

    Args:
        form_data: Twilio status callback form data
    """
    message_sid = form_data.get('MessageSid')
    message_status = form_data.get('MessageStatus')

    # Update message delivery status in database via update_message_status(tool)
    logger.info(f"WhatsApp message {message_sid} status: {message_status}")

    # TODO: Call database update via tool or direct query
    # await update_delivery_status(channel_message_id=message_sid, status=message_status)

    return {"status": "received"}


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)
    try:
        handler = WhatsAppHandler()
        logger.info("WhatsApp handler initialized successfully")
        # In production, webhook will be called by Twilio
    except ValueError as e:
        logger.error(f"Initialization failed: {e}")
