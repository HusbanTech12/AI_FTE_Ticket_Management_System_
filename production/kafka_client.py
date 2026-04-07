"""
Kafka Client for Customer Success FTE Event Streaming

Handles asynchronous message processing via Kafka topics:

Inbound topics (consumed):
- fte.tickets.incoming - Unified ticket queue from all channels
- fte.channels.email.inbound (legacy, mirrors above)
- fte.channels.whatsapp.inbound (legacy, mirrors above)
- fte.channels.webform.inbound (legacy, mirrors above)

Outbound topics (produced):
- fte.channels.email.outbound - Email responses to send
- fte.channels.whatsapp.outbound - WhatsApp responses to send
- fte.escalations - Escalated tickets for human agents
- fte.metrics - Performance metrics
- fte.dlq - Dead letter queue for failed messages

Requires:
- aiokafka for async consumers
- Kafka broker accessible at KAFKA_BOOTSTRAP_SERVERS
"""

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Callable, Awaitable

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from aiokafka.errors import KafkaError

logger = logging.getLogger(__name__)

# Topic definitions
TOPICS = {
    # Unified inbound tickets from all channels
    'tickets_incoming': 'fte.tickets.incoming',

    # Channel-specific inbound (optional, for debugging)
    'email_inbound': 'fte.channels.email.inbound',
    'whatsapp_inbound': 'fte.channels.whatsapp.inbound',
    'webform_inbound': 'fte.channels.webform.inbound',

    # Channel-specific outbound (responses)
    'email_outbound': 'fte.channels.email.outbound',
    'whatsapp_outbound': 'fte.channels.whatsapp.outbound',

    # Escalation queue
    'escalations': 'fte.escalations',

    # Metrics
    'metrics': 'fte.metrics',

    # Dead letter queue
    'dlq': 'fte.dlq'
}

# Default bootstrap servers
KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    'KAFKA_BOOTSTRAP_SERVERS',
    'localhost:9092'
)


class FTEKafkaProducer:
    """Async Kafka producer for FTE events."""

    def __init__(self):
        self.producer: Optional[AIOKafkaProducer] = None

    async def start(self):
        """Start the producer."""
        self.producer = AIOKafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda k: k.encode('utf-8') if k else None,
            acks='all',  # Wait for all replicas to acknowledge
            retries=3,
            enable_idempotence=True  # Exactly-once semantics
        )
        await self.producer.start()
        logger.info(f"Kafka producer started, connected to {KAFKA_BOOTSTRAP_SERVERS}")

    async def stop(self):
        """Stop the producer."""
        if self.producer:
            await self.producer.stop()
            self.producer = None
            logger.info("Kafka producer stopped")

    async def publish(self, topic: str, event: Dict[str, Any], key: str = None) -> bool:
        """
        Publish an event to a Kafka topic.

        Args:
            topic: Topic name or key from TOPICS
            event: Event data (dict, will be JSON serialized)
            key: Optional message key (for partitioning).

 Returns:
            True if successful
        """
        if not self.producer:
            logger.error("Producer not started")
            return False

        topic_name = TOPICS.get(topic, topic)

        try:
            # Add timestamp
            event['timestamp'] = datetime.utcnow().isoformat() + 'Z'

            future = await self.producer.send_and_wait(
                topic_name,
                value=event,
                key=key
            )
            logger.debug(f"Published event to {topic_name}: {event.get('event_type', 'unknown')}")
            return True

        except KafkaError as e:
            logger.error(f"Failed to publish to {topic_name}: {e}")
            return False

    async def publish_batch(self, topic: str, events: List[Dict[str, Any]]) -> List[bool]:
        """Publish multiple events to same topic."""
        results = []
        for event in events:
            results.append(await self.publish(topic, event))
        return results


class FTEKafkaConsumer:
    """Async Kafka consumer for FTE topics."""

    def __init__(
        self,
        topics: List[str],
        group_id: str,
        auto_offset_reset: str = 'latest',
        enable_auto_commit: bool = True
    ):
        """
        Initialize consumer.

        Args:
            topics: List of topic names or TOPICS keys
            group_id: Consumer group ID
            auto_offset_reset: 'earliest' or 'latest'
            enable_auto_commit: Auto-commit offsets (True for simplicity)
        """
        self.topics = [TOPICS.get(t, t) for t in topics]
        self.group_id = group_id
        self.auto_offset_reset = auto_offset_reset
        self.enable_auto_commit = enable_auto_commit
        self.consumer: Optional[AIOKafkaConsumer] = None
        self._handler: Optional[Callable[[str, Dict[str, Any]], Awaitable[None]]] = None

    async def start(self):
        """Start the consumer."""
        self.consumer = AIOKafkaConsumer(
            *self.topics,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id=self.group_id,
            auto_offset_reset=self.auto_offset_reset,
            enable_auto_commit=self.enable_auto_commit,
            value_deserializer=lambda v: json.loads(v.decode('utf-8')),
            key_deserializer=lambda k: k.decode('utf-8') if k else None,
            max_poll_records=10,  # Batch processing
            session_timeout_ms=10000,
            heartbeat_interval_ms=3000
        )
        await self.consumer.start()
        logger.info(f"Kafka consumer started, listening to {self.topics} as group '{self.group_id}'")

    async def stop(self):
        """Stop the consumer."""
        if self.consumer:
            await self.consumer.stop()
            self.consumer = None
            logger.info(f"Kafka consumer stopped (group: {self.group_id})")

    async def consume(self, handler: Callable[[str, Dict[str, Any]], Awaitable[None]]):
        """
        Start consuming messages and passing to handler.

        Args:
            handler: Async function(topic, message) to process each message
        """
        self._handler = handler
        logger.info(f"Starting consumer loop for topics: {self.topics}")

        try:
            async for msg in self.consumer:
                try:
                    topic = msg.topic
                    message = msg.value
                    key = msg.key

                    logger.debug(f"Received message from {topic} with key {key}: {message.get('event_type', 'unknown')}")

                    # Process message
                    await handler(topic, message)

                    # Commit if enabled
                    if self.enable_auto_commit:
                        await self.consumer.commit()

                except Exception as e:
                    logger.error(f"Error processing message: {e}", exc_info=True)
                    # In production, might send to DLQ or retry

        except asyncio.CancelledError:
            logger.info("Consumer cancelled")
        except Exception as e:
            logger.error(f"Consumer error: {e}", exc_info=True)
            raise

    async def get_watermarks(self) -> Dict[str, Any]:
        """Get current partition offsets (for monitoring)."""
        if not self.consumer:
            return {}
        return self.consumer.assignment()


async def test_kafka_connection():
    """Quick test to verify Kafka connectivity."""
    producer = FTEKafkaProducer()
    await producer.start()

    test_event = {
        'event_type': 'test',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
        'message': 'Kafka connectivity test'
    }

    success = await producer.publish('metrics', test_event, key='test')
    if success:
        logger.info("✅ Kafka connection successful")
    else:
        logger.error("❌ Kafka connection failed")

    await producer.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import asyncio
    asyncio.run(test_kafka_connection())
