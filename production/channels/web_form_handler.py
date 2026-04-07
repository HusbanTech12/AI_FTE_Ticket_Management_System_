"""
Web Support Form Handler

Provides FastAPI endpoints for web form submission and ticket lookup.
This is the required complete form UI integration.

The form component itself lives in frontend/web-form/SupportForm.jsx (React)
"""

import logging
import uuid
from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, Depends
from pydantic import BaseModel, EmailStr, Field, validator

from kafka_client import FTEKafkaProducer, TOPICS
from database.queries import create_ticket as create_ticket_record, get_pool, DBChannel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/support", tags=["support-form"])


# ============================================================================
# PYDANTIC MODELS (Request/Response schemas)
# ============================================================================

class SupportFormSubmission(BaseModel):
    """Inbound support form submission from frontend."""
    name: str = Field(..., min_length=2, max_length=200, description="Customer's full name")
    email: EmailStr = Field(..., description="Customer email address")
    subject: str = Field(..., min_length=5, max_length=300, description="Ticket subject/topic")
    category: str = Field(..., description="Issue category: general, technical, billing, feedback, bug_report")
    message: str = Field(..., min_length=10, max_length=3000, description="Detailed message")
    priority: str = Field("medium", description="Priority: low, medium, high")
    attachments: Optional[List[str]] = Field(default_factory=list, description="Base64 encoded attachment data")

    @validator('category')
    def category_must_be_valid(cls, v):
        valid_categories = ['general', 'technical', 'billing', 'feedback', 'bug_report']
        if v not in valid_categories:
            raise ValueError(f"Category must be one of: {valid_categories}")
        return v

    @validator('priority')
    def priority_must_be_valid(cls, v):
        valid = ['low', 'medium', 'high']
        if v not in valid:
            raise ValueError(f"Priority must be one of: {valid}")
        return v

    @validator('message')
    def message_min_length(cls, v):
        if len(v.strip()) < 10:
            raise ValueError('Message must be at least 10 characters')
        return v.strip()


class SupportFormResponse(BaseModel):
    """Immediate response to form submission."""
    ticket_id: str = Field(..., description="Unique ticket identifier")
    message: str = Field(..., description="Human-readable confirmation message")
    estimated_response_time: str = Field("Usually within 5 minutes", description="Expected response timeframe")


class TicketStatusResponse(BaseModel):
    """Response for ticket status lookup."""
    ticket_id: str
    status: str
    messages: List[dict]
    created_at: str
    last_updated: str
    channel: Optional[str] = None


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/submit", response_model=SupportFormResponse)
async def submit_support_form(
    submission: SupportFormSubmission,
    background_tasks: BackgroundTasks,
    producer: FTEKafkaProducer = Depends(get_kafka_producer)
):
    """
    Handle support form submission.

    This endpoint:
    1. Validates the submission
    2. Creates a ticket record in database
    3. Publishes to Kafka for agent processing
    4. Returns immediate confirmation with ticket ID

    The AI agent will respond asynchronously via the appropriate channel (email).
    """
    try:
        # Generate ticket ID
        ticket_id = str(uuid.uuid4())

        # Create normalized message for agent
        message_data = {
            'channel': 'web_form',
            'channel_message_id': ticket_id,
            'customer_email': submission.email,
            'customer_name': submission.name,
            'subject': submission.subject,
            'content': submission.message,
            'category': submission.category,
            'priority': submission.priority,
            'received_at': datetime.utcnow().isoformat() + 'Z',
            'metadata': {
                'form_version': '1.0',
                'attachments': submission.attachments,
                'user_agent': 'web-form'  # Would be extracted from request headers
            }
        }

        # Create initial ticket record in database
        try:
            pool = await get_pool()
            async with pool.acquire() as conn:
                # Resolve/create customer
                customer_id = await conn.fetchval(
                    "INSERT INTO customers (email, name) VALUES ($1, $2) ON CONFLICT (email) DO UPDATE SET name = $2 RETURNING id",
                    submission.email, submission.name
                )

                # Create conversation
                conversation_id = await conn.fetchval(
                    "INSERT INTO conversations (customer_id, initial_channel, status, subject) VALUES ($1, $2, 'active', $3) RETURNING id",
                    customer_id, 'web_form', submission.subject
                )

                # Create ticket
                await conn.execute(
                    """INSERT INTO tickets (id, conversation_id, customer_id, source_channel, category, priority, subject)
                       VALUES ($1, $2, $3, $4, $5, $6, $7)""",
                    uuid.UUID(ticket_id), conversation_id, customer_id, 'web_form',
                    submission.category, submission.priority, submission.subject
                )

                logger.info(f"Created ticket {ticket_id} for web form submission from {submission.email}")

        except Exception as db_error:
            logger.error(f"Failed to create ticket record: {db_error}")
            # Continue anyway - will still publish to Kafka

        # Publish to Kafka for agent processing (asynchronous)
        await producer.publish(
            TOPICS['tickets_incoming'],
            message_data,
            key=submission.email
        )

        logger.info(f"Published web form submission {ticket_id} to Kafka")

        return SupportFormResponse(
            ticket_id=ticket_id,
            message="Thank you for contacting us! Our AI assistant will review your request and respond via email within 5 minutes. You'll receive a response shortly.",
            estimated_response_time="Usually within 5 minutes"
        )

    except ValueError as ve:
        # Validation error
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error processing web form: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process submission. Please try again.")


@router.get("/ticket/{ticket_id}", response_model=TicketStatusResponse)
async def get_ticket_status(ticket_id: str):
    """
    Get status and conversation history for a ticket.

    Allows customers to check the status of their support request
    and view the conversation thread.
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Get ticket
            ticket = await conn.fetchrow(
                "SELECT * FROM tickets WHERE id = $1",
                uuid.UUID(ticket_id)
            )
            if not ticket:
                raise HTTPException(status_code=404, detail="Ticket not found")

            # Get conversation and messages
            conversation = await conn.fetchrow(
                "SELECT * FROM conversations WHERE id = $1",
                ticket['conversation_id']
            )

            messages = []
            if conversation:
                msgs = await conn.fetch("""
                    SELECT channel, direction, role, content, created_at, delivery_status
                    FROM messages
                    WHERE conversation_id = $1
                    ORDER BY created_at ASC
                """, conversation['id'])
                messages = [dict(m) for m in msgs]

            return TicketStatusResponse(
                ticket_id=ticket_id,
                status=ticket['status'],
                messages=messages,
                created_at=ticket['created_at'].isoformat() if ticket['created_at'] else None,
                last_updated=ticket['resolved_at'].isoformat() if ticket['resolved_at'] else ticket['created_at'].isoformat(),
                channel=ticket['source_channel']
            )

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid ticket ID format")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get ticket {ticket_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve ticket")


@router.get("/status")
async def form_status():
    """Check if web form API is operational."""
    return {
        "status": "operational",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "web-form-api"
    }


# ============================================================================
# HELPER FUNCTIONS (would be in a service layer in larger apps)
# ============================================================================

# Already inlined above to keep single-file simplicity


logger.info("Web form handler loaded")
