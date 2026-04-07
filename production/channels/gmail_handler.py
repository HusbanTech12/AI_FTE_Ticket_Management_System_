"""
Gmail Channel Handler

Handles incoming Gmail messages via Gmail API (push notifications via Pub/Sub)
and sends replies via Gmail API.

Prerequisites:
- Service account with Gmail API enabled
- Domain-wide delegation (for Business accounts) OR OAuth for individual accounts
- Pub/Sub topic configured for Gmail push notifications
"""

import os
import base64
import email as email_parser
from email.mime.text import MIMEText
from datetime import datetime
from typing import Dict, Any, Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from google.cloud import pubsub_v1
import asyncio
import logging

logger = logging.getLogger(__name__)

# Scopes for Gmail API
GMAIL_SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.modify'
]


class GmailHandler:
    """Handler for Gmail integration."""

    def __init__(self, credentials_path: str = None, user_email: str = None):
        """
        Initialize Gmail handler.

        Args:
            credentials_path: Path to service account JSON key
            user_email: Email to delegate to (for service account delegation)
        """
        self.credentials_path = credentials_path or os.getenv('GMAIL_CREDENTIALS_PATH', '/secrets/gmail-service-account.json')
        self.user_email = user_email or os.getenv('GMAIL_USER_EMAIL')
        self.service = None
        self._init_service()

    def _init_service(self):
        """Initialize Gmail API service."""
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=GMAIL_SCOPES
            )

            if self.user_email:
                # Delegation for domain-wide delegation
                delegated_credentials = credentials.with_subject(self.user_email)
                self.service = build('gmail', 'v1', credentials=delegated_credentials)
            else:
                self.service = build('gmail', 'v1', credentials=credentials)

            logger.info("Gmail service initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Gmail service: {e}")
            raise

    async def setup_push_notifications(self, topic_name: str, label_id: str = 'INBOX') -> Dict[str, Any]:
        """
        Set up Gmail push notifications via Pub/Sub.

        Args:
            topic_name: GCP Pub/Sub topic name (e.g., 'projects/my-project/topics/gmail-notifications')
            label_id: Which labels to watch (default INBOX)

        Returns:
            Watch response with history ID
        """
        request = {
            'labelIds': [label_id],
            'topicName': topic_name,
            'labelFilterAction': 'include'
        }

        try:
            result = self.service.users().watch(userId='me', body=request).execute()
            logger.info(f"Gmail push notifications set up. History ID: {result.get('historyId')}")
            return result
        except Exception as e:
            logger.error(f"Failed to setup Gmail watch: {e}")
            return {}

    async def process_notification(self, pubsub_message: Dict[str, Any]) -> list[Dict[str, Any]]:
        """
        Process incoming Pub/Sub notification from Gmail.

        Args:
            pubsub_message: Parsed Pub/Sub message containing notification data

        Returns:
            List of parsed message dictionaries ready for Kafka ingestion
        """
        if 'emailAddress' not in pubsub_message:
            logger.warning("Notification missing emailAddress")
            return []

        history_id = pubsub_message.get('historyId')
        if not history_id:
            logger.warning("Notification missing historyId")
            return []

        try:
            # Get new messages since last history ID
            history = self.service.users().history().list(
                userId='me',
                startHistoryId=history_id,
                historyTypes=['messageAdded']
            ).execute()

            messages = []
            for record in history.get('history', []):
                for msg_added in record.get('messagesAdded', []):
                    msg_id = msg_added['message']['id']
                    message_data = await self._fetch_and_parse_message(msg_id)
                    if message_data:
                        messages.append(message_data)

            logger.info(f"Processed {len(messages)} new Gmail messages")
            return messages

        except Exception as e:
            logger.error(f"Failed to process Gmail notification: {e}")
            return []

    async def _fetch_and_parse_message(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Fetch and parse a single Gmail message."""
        try:
            msg = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()

            headers = {h['name']: h['value'] for h in msg.get('payload', {}).get('headers', [])}

            # Extract body
            body = self._extract_body(msg.get('payload', {}))

            # Parse From header to get sender email
            from_header = headers.get('From', '')
            sender_email = self._extract_email(from_header)

            return {
                'channel': 'email',
                'channel_message_id': message_id,
                'thread_id': msg.get('threadId'),
                'customer_email': sender_email,
                'subject': headers.get('Subject', '(no subject)'),
                'content': body,
                'received_at': datetime.utcnow().isoformat() + 'Z',
                'metadata': {
                    'headers': headers,
                    'labels': msg.get('labelIds', []),
                    'snippet': msg.get('snippet', '')
                }
            }

        except Exception as e:
            logger.error(f"Failed to fetch message {message_id}: {e}")
            return None

    def _extract_body(self, payload: Dict[str, Any]) -> str:
        """Extract text/plain body from email payload."""
        if 'body' in payload and payload['body'].get('data'):
            return base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8')

        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('mimeType') == 'text/plain':
                    data = part.get('body', {}).get('data', '')
                    if data:
                        return base64.urlsafe_b64decode(data).decode('utf-8')
                # Recursively check nested parts
                if 'parts' in part:
                    nested_body = self._extract_body(part)
                    if nested_body:
                        return nested_body

        return ''

    def _extract_email(self, from_header: str) -> str:
        """Extract email address from 'Name <email@domain.com>' header."""
        import re
        match = re.search(r'<([^>]+)>', from_header)
        if match:
            return match.group(1)
        return from_header.strip()

    async def send_reply(
        self,
        to_email: str,
        subject: str,
        body: str,
        thread_id: str = None,
        in_reply_to: str = None
    ) -> Dict[str, Any]:
        """
        Send email reply.

        Args:
            to_email: Recipient email address
            subject: Email subject (will prepend 'Re:' if not already)
            body: Email body (plain text)
            thread_id: Thread ID to maintain conversation
            in_reply_to: Message ID to reply to (optional)

        Returns:
            Dict with message ID and delivery status
        """
        message = MIMEText(body, 'plain', 'utf-8')
        message['to'] = to_email

        # Correctly format subject with Re: prefix
        if subject.lower().startswith('re:'):
            message['subject'] = subject
        else:
            message['subject'] = f"Re: {subject}"

        # References for threading
        if thread_id:
            try:
                thread_msg = self.service.users().messages().get(
                    userId='me', id=thread_id
                ).execute()
                message_id = thread_msg.get('payload', {}).get('headers', [{}])[0].get('messageId')
                if message_id:
                    message['In-Reply-To'] = message_id
                    message['References'] = message_id
            except:
                pass  # Thread ID doesn't guarantee we can get message ID

        raw_bytes = base64.urlsafe_b64encode(message.as_bytes())
        raw_string = raw_bytes.decode('utf-8')

        body = {'raw': raw_string}
        if thread_id:
            body['threadId'] = thread_id

        try:
            result = self.service.users().messages().send(
                userId='me',
                body=body
            ).execute()
            return {
                'channel_message_id': result.get('id'),
                'delivery_status': 'sent',
                'thread_id': result.get('threadId')
            }
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return {
                'channel_message_id': None,
                'delivery_status': 'failed',
                'error': str(e)
            }

    async def mark_as_read(self, message_id: str):
        """Mark a Gmail message as read."""
        try:
            self.service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
        except Exception as e:
            logger.warning(f"Failed to mark message {message_id} as read: {e}")


# Standalone test function
async def test_gmail_handler():
    """Manually test Gmail integration (requires credentials)."""
    credentials_path = os.getenv('GMAIL_CREDENTIALS_PATH')
    if not credentials_path or not os.path.exists(credentials_path):
        logger.error("GMAIL_CREDENTIALS_PATH not set or file not found")
        return

    handler = GmailHandler(credentials_path=credentials_path, user_email="support@flowsync.com")

    # Test: Check inbox label
    try:
        profile = handler.service.users().getProfile(userId='me').execute()
        logger.info(f"Authenticated as: {profile.get('emailAddress')}")
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        return

    # Test: List 5 recent messages
    try:
        results = handler.service.users().messages().list(
            userId='me',
            labelIds=['INBOX'],
            maxResults=5
        ).execute()
        messages = results.get('messages', [])
        logger.info(f"Found {len(messages)} recent inbox messages")

        for msg in messages[:2]:
            msg_data = handler.service.users().messages().get(userId='me', id=msg['id']).execute()
            headers = {h['name']: h['value'] for h in msg_data.get('payload', {}).get('headers', [])}
            logger.info(f"Message: Subject='{headers.get('Subject', '')}' From='{headers.get('From', '')}'")
    except Exception as e:
        logger.error(f"Failed to list messages: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_gmail_handler())
