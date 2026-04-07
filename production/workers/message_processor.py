"""
Unified Message Processor Worker

Consumes tickets from Kafka and processes them through the Customer Success FTE agent.
This is the core worker that runs 24/7 on Kubernetes.

Responsibilities:
- Consume messages from all channel topics (unified via fte.tickets.incoming)
- Resolve or create customers
- Create/get conversations
- Store inbound messages
- Run agent processing
- Store agent responses
- Publish outbound messages to channel-specific topics
- Publish metrics
- Handle errors gracefully
"""

import os
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any

from kafka_client import FTEKafkaConsumer, FTEKafkaProducer, TOPICS
from agent.customer_success_agent import run_agent, AgentResponse
from channels.gmail_handler import GmailHandler
from channels.whatsapp_handler import WhatsAppHandler
from database.queries import (
    get_pool, resolve_or_create_customer,
    get_or_create_conversation, store_message as store_message_in_db,
    Channel as DBChannel, record_metric
)

logger = logging.getLogger(__name__)


class UnifiedMessageProcessor:
    """Main worker that processes all incoming customer messages."""

    def __init__(self):
        self.gmail = None
        self.whatsapp = None
        self.producer = None
        self.running = False

    async def initialize_channel_handlers(self):
        """Initialize channel-specific handlers (for response sending)."""
        try:
            # Gmail handler (optional - only needed if sending emails)
            if os.getenv('GMAIL_CREDENTIALS_PATH'):
                self.gmail = GmailHandler()
                logger.info("Gmail handler initialized")
        except Exception as e:
            logger.warning(f"Gmail handler not initialized: {e}")

        try:
            # WhatsApp handler (optional)
            self.whatsapp = WhatsAppHandler()
            logger.info("WhatsApp handler initialized")
        except Exception as e:
            logger.warning(f"WhatsApp handler not initialized: {e}")

    async def start(self):
        """Start the message processor worker."""
        logger.info("Starting Unified Message Processor...")

        # Initialize handlers
        await self.initialize_channel_handlers()

        # Initialize Kafka producer
        self.producer = FTEKafkaProducer()
        await self.producer.start()

        # Create consumer for inbound tickets
        consumer = FTEKafkaConsumer(
            topics=['tickets_incoming'],
            group_id='fte-message-processor',
            auto_offset_reset='latest',
            enable_auto_commit=False  # Manual commit after successful processing
        )
        await consumer.start()

        logger.info("Message processor started, listening for tickets...")
        self.running = True

        try:
            await consumer.consume(self.process_message)
        except asyncio.CancelledError:
            logger.info("Processor stopped by cancellation")
        except Exception as e:
            logger.error(f"Processor crashed: {e}", exc_info=True)
            raise
        finally:
            await self.shutdown()
            await consumer.stop()
            await self.producer.stop()

    async def shutdown(self):
        """Graceful shutdown."""
        self.running = False
        logger.info("Shutting down message processor...")

    async def process_message(self, topic: str, message: dict):
        """
        Process a single incoming message from any channel.

        This is the main pipeline:
        1. Extract channel & normalize message
        2. Resolve/create customer
        3. Get/create conversation
        4. Store inbound message in DB
        5. Run agent
        6. Store agent response
        7. Send response via appropriate channel
        8. Publish metrics
        """
        start_time = datetime.utcnow()
        conversation_id = None
        ticket_id = None

        try:
            # Extract channel
            channel_str = message.get('channel', 'email')
            channel = DBChannel(channel_str)

            logger.info(f"Processing {channel_str} message: {message.get('subject', '')[:50]}")

            # Step 1: Resolve or create customer
            customer_id = await self.resolve_customer(message)
            logger.debug(f"Resolved customer: {customer_id}")

            # Step 2: Get or create conversation
            subject = message.get('subject', 'Support Request')
            conversation_id = await get_or_create_conversation(
                customer_id=customer_id,
                channel=channel,
                subject=subject
            )

            # Step 3: Store inbound message
            inbound_content = message.get('content', '')
            channel_message_id = message.get('channel_message_id')

            message_id = await store_message_in_db(
                conversation_id=conversation_id,
                channel=channel,
                direction='inbound',
                role='customer',
                content=inbound_content,
                channel_message_id=channel_message_id
            )
            logger.debug(f"Stored inbound message: {message_id}")

            # Step 4: Load conversation history
            history = await self.load_conversation_history(conversation_id)

            # Step 5: Run agent
            agent_response: AgentResponse = await run_agent(
                message=inbound_content,
                channel=channel.value,
                customer_id=customer_id,
                conversation_id=conversation_id,
                subject=subject,
                metadata=message.get('metadata', {})
            )

            # Step 6: Store agent response
            processing_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            await store_message_in_db(
                conversation_id=conversation_id,
                channel=channel,
                direction='outbound',
                role='agent',
                content=agent_response.output,
                latency_ms=int(processing_time_ms),
                tool_calls=agent_response.tool_calls,
                sentiment_score=agent_response.sentiment
            )

            # Step 7: Send response via appropriate channel (if not escalated)
            if not agent_response.escalated:
                delivery_status = await self.send_response(
                    channel=channel,
                    ticket_id=ticket_id or "TBD",  # Would get from create_ticket tool call
                    message=agent_response.output,
                    customer_data=self.extract_customer_data(message)
                )
                logger.info(f"Response sent via {channel.value}: {delivery_status}")
            else:
                # Escalation: publish to escalation topic
                await self.producer.publish(
                    'escalations',
                    {
                        'event_type': 'ticket_escalated',
                        'ticket_id': ticket_id,
                        'customer_id': customer_id,
                        'conversation_id': conversation_id,
                        'channel': channel.value,
                        'reason': agent_response.escalation_reason,
                        'timestamp': datetime.utcnow().isoformat() + 'Z'
                    }
                )
                logger.info(f"Ticket escalated: {ticket_id or 'pending'}")

            # Step 8: Publish metrics
            await self.publish_metrics(
                channel=channel.value,
                processing_time_ms=processing_time_ms,
                escalated=agent_response.escalated,
                message_length=len(inbound_content),
                response_length=len(agent_response.output),
                tool_calls_count=len(agent_response.tool_calls or [])
            )

            latency_total = (datetime.utcnow() - start_time).total_seconds() * 1000
            logger.info(f"Processed {channel_str} message in {latency_total:.0f}ms (escalated={agent_response.escalated})")

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            await self.handle_error(message, e)

    async def resolve_customer(self, message: dict) -> str:
        """
        Resolve existing customer or create new one from message.

        Strategy:
        1. If email present, lookup by email
        2. If phone present, lookup by phone/whatsapp identifier
        3. If not found, create new customer
        """
        email = message.get('customer_email')
        phone = message.get('customer_phone')
        name = message.get('customer_name')

        pool = await get_pool()
        async with pool.acquire() as conn:
            # Try email first
            if email:
                customer = await conn.fetchrow(
                    "SELECT id FROM customers WHERE email = $1",
                    email
                )
                if customer:
                    return str(customer['id'])

                # Create new
                customer_id = await conn.fetchval(
                    "INSERT INTO customers (email, name) VALUES ($1, $2) RETURNING id",
                    email, name or ""
                )
                # Also add identifier record
                await conn.execute(
                    """INSERT INTO customer_identifiers (customer_id, identifier_type, identifier_value)
                       VALUES ($1, 'email', $2)
                       ON CONFLICT (identifier_type, identifier_value) DO NOTHING""",
                    customer_id, email
                )
                logger.info(f"Created new customer {customer_id} from email {email}")
                return str(customer_id)

            # Try phone
            if phone:
                identifier = await conn.fetchrow(
                    """SELECT customer_id FROM customer_identifiers
                       WHERE identifier_value = $1
                       AND identifier_type IN ('phone', 'whatsapp')""",
                    phone
                )
                if identifier:
                    return str(identifier['customer_id'])

                # Create new
                customer_id = await conn.fetchval(
                    "INSERT INTO customers (phone, name) VALUES ($1, $2) RETURNING id",
                    phone, name or ""
                )
                await conn.execute(
                    """INSERT INTO customer_identifiers (customer_id, identifier_type, identifier_value)
                       VALUES ($1, 'whatsapp', $2)
                       ON CONFLICT DO NOTHING""",
                    customer_id, phone
                )
                logger.info(f"Created new customer {customer_id} from phone {phone}")
                return str(customer_id)

        raise ValueError(f"Could not resolve customer from message: {message}")

    async def load_conversation_history(self, conversation_id: str, limit: int = 10) -> list:
        """Load recent messages for context."""
        # For simplified prototype, return empty history
        # In full implementation: query messages table and format for OpenAI messages
        query = """
            SELECT role, content, created_at
            FROM messages
            WHERE conversation_id = $1
            ORDER BY created_at DESC
            LIMIT $2
        """
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, conversation_id, limit)
            history = []
            for row in reversed(rows):  # Chronological order
                history.append({
                    "role": row['role'],
                    "content": row['content']
                })
            return history

    def extract_customer_data(self, message: dict) -> Dict[str, Any]:
        """Extract customer contact info for response sending."""
        return {
            'email': message.get('customer_email'),
            'phone': message.get('customer_phone'),
            'name': message.get('customer_name')
        }

    async def send_response(self, channel: DBChannel, ticket_id: str, message: str, customer_data: Dict[str, Any]) -> str:
        """
        Send response via appropriate channel.

        Returns delivery status.
        """
        try:
            if channel == DBChannel.EMAIL:
                if not self.gmail:
                    logger.warning("Gmail handler not available, skipping send")
                    return "gmail_not_configured"

                to_email = customer_data.get('email')
                if not to_email:
                    raise ValueError("No customer email for email response")

                result = await self.gmail.send_reply(
                    to_email=to_email,
                    subject=f"Re: Support Ticket {ticket_id}",
                    body=message
                )
                return result.get('delivery_status', 'unknown')

            elif channel == DBChannel.WHATSAPP:
                if not self.whatsapp:
                    logger.warning("WhatsApp handler not available, skipping send")
                    return "whatsapp_not_configured"

                to_phone = customer_data.get('phone')
                if not to_phone:
                    raise ValueError("No customer phone for WhatsApp response")

                result = await self.whatsapp.send_message(
                    to_phone=to_phone,
                    body=message
                )
                return result.get('delivery_status', 'unknown')

            else:  # web_form
                # Web form responses come via email notification or API
                to_email = customer_data.get('email')
                if to_email:
                    # Send email notification
                    # In production, would use SMTP or SendGrid
                    logger.info(f"Web form response would be emailed to {to_email}")
                    return "email_queued"
                return "no_email"

        except Exception as e:
            logger.error(f"Failed to send response via {channel.value}: {e}")
            return f"failed: {str(e)}"

    async def publish_metrics(
        self,
        channel: str,
        processing_time_ms: float,
        escalated: bool,
        message_length: int,
        response_length: int,
        tool_calls_count: int
    ):
        """Publish processing metrics to Kafka."""
        metrics = [
            {
                'event_type': 'message_processed',
                'channel': channel,
                'metric_name': 'processing_time_ms',
                'metric_value': processing_time_ms
            },
            {
                'event_type': 'message_processed',
                'channel': channel,
                'metric_name': 'escalated',
                'metric_value': 1.0 if escalated else 0.0
            },
            {
                'event_type': 'message_processed',
                'channel': channel,
                'metric_name': 'message_length',
                'metric_value': message_length
            },
            {
                'event_type': 'message_processed',
                'channel': channel,
                'metric_name': 'response_length',
                'metric_value': response_length
            },
            {
                'event_type': 'message_processed',
                'channel': channel,
                'metric_name': 'tool_calls_count',
                'metric_value': tool_calls_count
            }
        ]

        for metric in metrics:
            await self.producer.publish(
                'metrics',
                metric,
                key=f"{channel}:{metric['metric_name']}"
            )

    async def handle_error(self, message: dict, error: Exception):
        """
        Handle processing errors gracefully.

        Sends apology response if possible, publishes to DLQ.
        """
        channel_str = message.get('channel', 'email')
        customer_email = message.get('customer_email')
        customer_phone = message.get('customer_phone')

        apology = "I apologize, but I'm experiencing technical difficulties processing your request. A human agent will follow up with you shortly."

        logger.error(f"Sending error apology for {channel_str} message from {customer_email or customer_phone}: {error}")

        try:
            # Attempt to send apology
            if channel_str == 'email' and customer_email and self.gmail:
                await self.gmail.send_reply(
                    to_email=customer_email,
                    subject="Urgent: Issue with your support request",
                    body=apology
                )
            elif channel_str == 'whatsapp' and customer_phone and self.whatsapp:
                await self.whatsapp.send_message(
                    to_phone=customer_phone,
                    body=apology
                )
        except Exception as send_error:
            logger.error(f"Failed to send error apology: {send_error}")

        # Publish to DLQ for later analysis
        await self.producer.publish(
            'dlq',
            {
                'event_type': 'processing_error',
                'original_message': message,
                'error': str(error),
                'timestamp': datetime.utcnow().isoformat() + 'Z',
                'requires_human': True
            }
        )


async def main():
    """Entry point for worker process."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    processor = UnifiedMessageProcessor()
    await processor.start()


if __name__ == "__main__":
    asyncio.run(main())
