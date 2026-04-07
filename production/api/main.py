"""
FastAPI Service for Customer Success FTE

Provides:
- Webhook endpoints for all channels (Gmail, WhatsApp, Web Form)
- Health checks and monitoring
- Conversation and customer lookup APIs
- Channel metrics endpoints
- Support for frontend web form submission

Runs on Kubernetes as the API ingress layer.
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, BackgroundTasks, Request, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, validator
import uvicorn

from kafka_client import FTEKafkaProducer, TOPICS
from database.queries import get_pool, Channel as DBChannel

# Local imports
from channels.gmail_handler import GmailHandler
from channels.whatsapp_handler import WhatsAppHandler

logger = logging.getLogger(__name__)

# ============================================================================
# FASTAPI APP SETUP
# ============================================================================

app = FastAPI(
    title="Customer Success FTE API",
    description="24/7 AI-powered customer support across Email, WhatsApp, and Web",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS for web form frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# SINGLETON INITIALIZATION (lazy)
# ============================================================================

_kafka_producer: Optional[FTEKafkaProducer] = None
_gmail_handler: Optional[GmailHandler] = None
_whatsapp_handler: Optional[WhatsAppHandler] = None


async def get_kafka_producer() -> FTEKafkaProducer:
    """Dependency: get initialized Kafka producer."""
    global _kafka_producer
    if _kafka_producer is None:
        _kafka_producer = FTEKafkaProducer()
        await _kafka_producer.start()
    return _kafka_producer


async def get_gmail_handler() -> Optional[GmailHandler]:
    """Dependency: get Gmail handler if configured."""
    global _gmail_handler
    if _gmail_handler is None:
        try:
            if os.getenv('GMAIL_CREDENTIALS_PATH'):
                _gmail_handler = GmailHandler()
        except Exception as e:
            logger.warning(f"Gmail handler not available: {e}")
    return _gmail_handler


async def get_whatsapp_handler() -> Optional[WhatsAppHandler]:
    """Dependency: get WhatsApp handler if configured."""
    global _whatsapp_handler
    if _whatsapp_handler is None:
        try:
            _whatsapp_handler = WhatsAppHandler()
        except Exception as e:
            logger.warning(f"WhatsApp handler not available: {e}")
    return _whatsapp_handler


# ============================================================================
# LIFECYCLE EVENTS
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize resources on startup."""
    logger.info("Starting Customer Success FTE API...")

    # Initialize Kafka producer (shared)
    await get_kafka_producer()

    # Initialize channel handlers (for webhook processing)
    await get_gmail_handler()
    await get_whatsapp_handler()

    logger.info("API startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down API...")

    global _kafka_producer, _gmail_handler, _whatsapp_handler

    if _kafka_producer:
        await _kafka_producer.stop()
        _kafka_producer = None

    # No explicit shutdown needed for channel handlers (they're stateless)

    logger.info("API shutdown complete")


# ============================================================================
# HEALTH & MONITORING ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """
    Health check endpoint for Kubernetes liveness/readiness probes.

    Checks:
    - Database connectivity
    - Kafka connectivity
    - Channel handlers status
    """
    health = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "components": {
            "api": "healthy",
            "database": "unknown",
            "kafka": "unknown",
            "gmail": "unavailable",
            "whatsapp": "unavailable"
        }
    }

    # Check database
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        health["components"]["database"] = "healthy"
    except Exception as e:
        health["components"]["database"] = f"unhealthy: {str(e)}"
        health["status"] = "degraded"

    # Check Kafka
    try:
        kafka = await get_kafka_producer()
        # Could optionally do a metadata check
        health["components"]["kafka"] = "healthy"
    except Exception as e:
        health["components"]["kafka"] = f"unhealthy: {str(e)}"
        health["status"] = "degraded"

    # Check channel handlers
    gmail = await get_gmail_handler()
    health["components"]["gmail"] = "healthy" if gmail else "not_configured"

    whatsapp = await get_whatsapp_handler()
    health["components"]["whatsapp"] = "healthy" if whatsapp else "not_configured"

    status_code = 200 if health["status"] == "healthy" else 503
    return JSONResponse(content=health, status_code=status_code)


@app.get("/metrics")
async def get_metrics(
    hours: int = 24,
    kafka: FTEKafkaProducer = Depends(get_kafka_producer)
):
    """
    Get performance metrics for last N hours.

    Args:
        hours: Number of hours to look back (default 24)

    Returns:
        Dict with channel metrics, throughput, latency stats
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    channel,
                    COUNT(*) FILTER (WHERE direction = 'inbound') as inbound_count,
                    COUNT(*) FILTER (WHERE direction = 'outbound') as outbound_count,
                    AVG(latency_ms) as avg_latency_ms,
                    COUNT(*) FILTER (WHERE delivery_status = 'failed') as failed_deliveries
                FROM messages
                WHERE created_at > NOW() - INTERVAL '${hours} hours'
                GROUP BY channel
            """, hours)

            metrics = {}
            for row in rows:
                metrics[row['channel']] = dict(row)

            return {
                "period_hours": hours,
                "generated_at": datetime.utcnow().isoformat() + "Z",
                "metrics": metrics
            }

    except Exception as e:
        logger.error(f"Failed to fetch metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# WEBHOOK ENDPOINTS
# ============================================================================

@app.post("/webhooks/gmail")
async def gmail_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    gmail: Optional[GmailHandler] = Depends(get_gmail_handler)
):
    """
    Gmail push notification webhook.

    Receives Pub/Sub push notification from Gmail API with new message data.
    Validates and forwards to Kafka for processing.

    Expected payload: Pub/Sub push format with 'message' containing base64 encoded data
    """
    if not gmail:
        raise HTTPException(status_code=503, detail="Gmail handler not configured")

    try:
        body = await request.json()
        logger.debug(f"Received Gmail notification: {body.keys()}")

        # Process notification (may batch multiple messages)
        messages = await gmail.process_notification(body)

        if not messages:
            return {"status": "no_new_messages", "count": 0}

        # Publish each message to Kafka
        producer = await get_kafka_producer()
        for msg in messages:
            await producer.publish(
                TOPICS['tickets_incoming'],
                msg,
                key=msg.get('customer_email')
            )

        logger.info(f"Published {len(messages)} Gmail messages to Kafka")

        return {"status": "processed", "count": len(messages)}

    except Exception as e:
        logger.error(f"Gmail webhook error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhooks/whatsapp")
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    whatsapp: Optional[WhatsAppHandler] = Depends(get_whatsapp_handler)
):
    """
    WhatsApp incoming message webhook (Twilio).

    Receives messages from Twilio WhatsApp. Validates signature, then pushes to Kafka.
    Returns empty TwiML response (200 OK) immediately - agent responds asynchronously.
    """
    if not whatsapp:
        raise HTTPException(status_code=503, detail="WhatsApp handler not configured")

    try:
        # Validate Twilio signature
        if not await whatsapp.validate_webhook(request):
            raise HTTPException(status_code=403, detail="Invalid signature")

        # Parse form data
        form_data = await request.form()
        message_data = await whatsapp.process_webhook(dict(form_data))

        # Publish to Kafka
        producer = await get_kafka_producer()
        await producer.publish(
            TOPICS['tickets_incoming'],
            message_data,
            key=message_data.get('customer_phone')
        )

        logger.info(f"Published WhatsApp message to Kafka from {message_data.get('customer_phone')}")

        # Immediate empty response (200 OK) - agent will reply separately
        return Response(
            content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
            media_type="application/xml"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"WhatsApp webhook error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/webhooks/whatsapp/status")
async def whatsapp_status_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    WhatsApp message status callback endpoint.

    Called by Twilio when message status changes (sent, delivered, read, failed).
    Used to update message delivery status in database.
    """
    try:
        form_data = await request.form()
        message_sid = form_data.get('MessageSid')
        status = form_data.get('MessageStatus')

        logger.debug(f"WhatsApp status update: {message_sid} -> {status}")

        # Update message status in DB (would call DB tool)
        # await update_message_delivery_status(channel_message_id=message_sid, status=status)

        # Publish metrics
        producer = await get_kafka_producer()
        await producer.publish(
            TOPICS['metrics'],
            {
                'event_type': 'message_delivery_status',
                'channel': 'whatsapp',
                'message_sid': message_sid,
                'status': status,
                'timestamp': datetime.utcnow().isoformat() + 'Z'
            }
        )

        return {"status": "recorded"}

    except Exception as e:
        logger.error(f"WhatsApp status webhook error: {e}")
        return {"status": "error", "detail": str(e)}


# ============================================================================
# DATA API ENDPOINTS
# ============================================================================

@app.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    include_messages: bool = True
):
    """
    Get full conversation history with cross-channel context.

    Args:
        conversation_id: UUID of conversation
        include_messages: Whether to include individual messages

    Returns:
        Dict with conversation metadata and optional message list
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Get conversation
            conv = await conn.fetchrow(
                "SELECT * FROM conversations WHERE id = $1",
                conversation_id
            )
            if not conv:
                raise HTTPException(status_code=404, detail="Conversation not found")

            conversation_data = dict(conv)

            # Include messages if requested
            if include_messages:
                messages = await conn.fetch("""
                    SELECT id, channel, direction, role, content, created_at,
                           delivery_status, sentiment_score
                    FROM messages
                    WHERE conversation_id = $1
                    ORDER BY created_at ASC
                """, conversation_id)
                conversation_data['messages'] = [dict(m) for m in messages]

            # Include customer info
            if conv['customer_id']:
                customer = await conn.fetchrow(
                    "SELECT email, name, company, tier FROM customers WHERE id = $1",
                    conv['customer_id']
                )
                if customer:
                    conversation_data['customer'] = dict(customer)

            # Include linked tickets
            tickets = await conn.fetch("""
                SELECT id, category, priority, status, created_at, resolved_at
                FROM tickets
                WHERE conversation_id = $1
                ORDER BY created_at DESC
            """, conversation_id)
            conversation_data['tickets'] = [dict(t) for t in tickets]

            return conversation_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get conversation {conversation_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/customers/lookup")
async def lookup_customer(
    email: Optional[str] = None,
    phone: Optional[str] = None
):
    """
    Look up customer by email or phone across all channels.

    Args:
        email: Customer email address
        phone: Customer phone number

    Returns:
        Customer profile with history summary
    """
    if not email and not phone:
        raise HTTPException(status_code=400, detail="Provide email or phone")

    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            query = "SELECT * FROM customers WHERE "
            params = []

            if email:
                query += "email = $1"
                params.append(email)
            if phone:
                if email:
                    query += " OR phone = $2"
                    params.append(phone)
                else:
                    query += "phone = $1"

            customer = await conn.fetchrow(query, *params)

            if not customer:
                raise HTTPException(status_code=404, detail="Customer not found")

            customer_data = dict(customer)

            # Get recent conversations
            conversations = await conn.fetch("""
                SELECT id, initial_channel, started_at, status, sentiment_score
                FROM conversations
                WHERE customer_id = $1
                ORDER BY started_at DESC
                LIMIT 5
            """, customer['id'])
            customer_data['recent_conversations'] = [dict(c) for c in conversations]

            # Get total stats
            stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_conversations,
                    COUNT(*) FILTER (WHERE status = 'escalated') as escalated_conversations,
                    AVG(sentiment_score) as avg_sentiment
                FROM conversations
                WHERE customer_id = $1
            """, customer['id'])
            customer_data['stats'] = dict(stats) if stats else {}

            return customer_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Lookup failed (email={email}, phone={phone}): {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tickets/{ticket_id}")
async def get_ticket(ticket_id: str):
    """Get ticket details with conversation and messages."""
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            ticket = await conn.fetchrow(
                "SELECT * FROM tickets WHERE id = $1",
                ticket_id
            )
            if not ticket:
                raise HTTPException(status_code=404, detail="Ticket not found")

            ticket_data = dict(ticket)

            # Get conversation
            if ticket['conversation_id']:
                conv = await conn.fetchrow(
                    "SELECT * FROM conversations WHERE id = $1",
                    ticket['conversation_id']
                )
                if conv:
                    ticket_data['conversation'] = dict(conv)

            # Get recent messages
            if ticket['conversation_id']:
                messages = await conn.fetch("""
                    SELECT channel, direction, role, content, created_at
                    FROM messages
                    WHERE conversation_id = $1
                    ORDER BY created_at DESC
                    LIMIT 20
                """, ticket['conversation_id'])
                ticket_data['messages'] = [dict(m) for m in messages]

            return ticket_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get ticket {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# KAFKA MANAGEMENT ENDPOINTS (admin/debug)
# ============================================================================

@app.get("/admin/kafka/topics")
async def list_kafka_topics():
    """List all Kafka topics (debug endpoint)."""
    # In production, would query Kafka broker's metadata
    return {
        "topics": list(TOPICS.values()),
        "descriptions": TOPICS
    }


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An internal error occurred",
            "request_id": id(request)  # In production, use proper request ID
        }
    )


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("DEBUG", "false").lower() == "true"
    )
