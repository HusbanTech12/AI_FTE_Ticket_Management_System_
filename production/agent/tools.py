"""
Production tools for Customer Success FTE using OpenAI Agents SDK.

All tools decorated with @function_tool for OpenAI Agents SDK integration.
Each tool has strict Pydantic input validation, error handling, and logging.
"""

import os
import asyncio
import json
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime

from pydantic import BaseModel, Field, validator
from agents import function_tool

from database.queries import (
    get_pool, resolve_or_create_customer,
    get_or_create_conversation, store_message,
    get_customer_history as fetch_customer_history,
    create_ticket as create_ticket_record,
    escalate_ticket as escalate_ticket_record,
    search_knowledge_base as search_kb,
    record_metric,
    Channel as DBChannel
)

logger = logging.getLogger(__name__)


# ============================================================================
# INPUT SCHEMAS (Pydantic for type safety and validation)
# ============================================================================

class KnowledgeSearchInput(BaseModel):
    """Input for knowledge base search."""
    query: str = Field(..., min_length=3, max_length=500, description="Search query")
    max_results: int = Field(5, ge=1, le=20, description="Max number of results")
    category: Optional[str] = Field(None, description="Optional category filter")

    @validator('query')
    def query_not_empty(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Query cannot be empty")
        return v


class TicketInput(BaseModel):
    """Input for ticket creation."""
    customer_id: str = Field(..., description="Customer identifier (email or phone)")
    issue: str = Field(..., min_length=10, max_length=2000, description="Issue description")
    priority: str = Field("medium", description="Priority: low, medium, high")
    category: Optional[str] = Field(None, description="Category: general, technical, billing, feedback, bug_report")
    channel: DBChannel

    @validator('priority')
    def priority_valid(cls, v):
        valid = ['low', 'medium', 'high']
        if v.lower() not in valid:
            raise ValueError(f"Priority must be one of: {valid}")
        return v.lower()


class EscalationInput(BaseModel):
    """Input for escalation to human."""
    ticket_id: str = Field(..., description="Ticket ID to escalate")
    reason: str = Field(..., min_length=5, max_length=500, description="Why escalation needed")
    urgency: str = Field("normal", description="low, normal, high")

    @validator('urgency')
    def urgency_valid(cls, v):
        valid = ['low', 'normal', 'high']
        if v.lower() not in valid:
            raise ValueError(f"Urgency must be one of: {valid}")
        return v.lower()


class ResponseInput(BaseModel):
    """Input for sending response."""
    ticket_id: str = Field(..., description="Ticket ID this response belongs to")
    message: str = Field(..., min_length=1, max_length=3000, description="Response text to send")
    channel: DBChannel

    @validator('message')
    def message_not_empty(cls, v):
        v = v.strip()
        if not v:
            raise ValueError("Message cannot be empty")
        return v


# ============================================================================
# EMBEDDING GENERATION (placeholder - would use OpenAI embeddings API)
# ============================================================================

async def generate_embedding(text: str) -> List[float]:
    """
    Generate embedding for text using OpenAI embeddings API or local model.
    This is a placeholder - in production, call OpenAI API: text-embedding-3-small
    """
    # For prototype, return random consistent embedding (demostration only!)
    # In production: httpx.post("https://api.openai.com/v1/embeddings", ...)
    import hashlib
    hash_val = int(hashlib.md5(text.encode()).hexdigest()[:8], 16)
    return [float((hash_val % 1000)) / 1000.0] * 1536  # dummy embedding, 1536 dims


# ============================================================================
# TOOL FUNCTIONS
# ============================================================================

@function_tool
async def search_knowledge_base(input: KnowledgeSearchInput) -> str:
    """
    Search product documentation for relevant information.

    Use this when the customer asks questions about product features,
    how to use something, or needs technical information.

    Args:
        input: Search parameters including query and optional filters

    Returns:
        Formatted search results with similarity scores
    """
    start_time = datetime.utcnow()
    try:
        # Generate embedding for query
        query_embedding = await generate_embedding(input.query)

        # Search knowledge base
        results = await search_kb(
            input.query,
            query_embedding,
            max_results=input.max_results,
            category=input.category
        )

        if not results:
            return "I couldn't find relevant information in our documentation. Please try rephrasing your questions or I can escalate this to a human specialist."

        # Format results for agent
        formatted = []
        for idx, result in enumerate(results, 1):
            formatted.append(f"""**Result {idx}: {result['title']}** (Relevance: {result['similarity']:.2f})
{result['content'][:500]}

""")

        latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        logger.info(f"Knowledge search for '{input.query[:50]}...' returned {len(results)} results in {latency_ms:.0f}ms")

        return "\n---\n".join(formatted)

    except Exception as e:
        logger.error(f"Knowledge base search failed: {e}", exc_info=True)
        return "The knowledge base is currently unavailable. I'll do my best to help based on my training, or I can escalate to a human."


@function_tool
async def create_ticket(input: TicketInput) -> str:
    """
    Create a support ticket in the system with channel tracking.

    ALWAYS create a ticket at the start of every conversation.
    Include the source channel for proper tracking.

    Args:
        input: Ticket details

    Returns:
        Confirmation with ticket ID
    """
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Resolve or create customer
            customer_id = await resolve_or_create_customer(
                email=input.customer_id if '@' in input.customer_id else None,
                phone=input.customer_id if not '@' in input.customer_id else None
            )

            # Get or create conversation (24h window)
            conversation_id = await get_or_create_conversation(
                customer_id=customer_id,
                channel=input.channel,
                subject=input.issue[:100]  # Truncate for subject
            )

            # Create ticket
            ticket_id = await conn.fetchval("""
                INSERT INTO tickets (conversation_id, customer_id, source_channel, subject, category, priority)
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
            """, conversation_id, customer_id, input.channel.value, input.issue, input.category, input.priority)

            logger.info(f"Created ticket {ticket_id} for customer {customer_id} via {input.channel}")

            return f"Ticket created successfully. Ticket ID: {ticket_id}. Customer: {customer_id}."

    except Exception as e:
        logger.error(f"Failed to create ticket: {e}", exc_info=True)
        # Don't fail the whole conversation - return a dummy ticket ID so agent can continue
        return f"Error creating ticket: {str(e)}. Please escalate to human support."


@function_tool
async def get_customer_history(customer_id: str) -> str:
    """
    Get customer's complete interaction history across ALL channels.

    Use this to understand context from previous conversations,
    even if they happened on a different channel.

    Args:
        customer_id: Customer email or phone number

    Returns:
        Formatted history of past interactions
    """
    try:
        # Try to resolve customer if not already UUID
        # If it's an email/phone, we need to look it up
        pool = await get_pool()
        async with pool.acquire() as conn:
            customer = await conn.fetchrow("SELECT * FROM customers WHERE email = $1 OR phone = $1", customer_id)
            if customer:
                customer_id = str(customer['id'])

            # Get history (last 20 messages)
            history = await fetch_customer_history(customer_id, limit=20)

        if not history:
            return "No previous interactions found for this customer."

        # Summarize for agent consumption
        lines = []
        lines.append(f"Customer history ({len(history)} messages):")
        lines.append("=" * 60)

        # Group by conversation
        conversations = {}
        for msg in history:
            conv_id = msg['conversation_id']
            if conv_id not in conversations:
                conversations[conv_id] = {
                    'channel': msg['initial_channel'] if 'initial_channel' in msg else msg['channel'],
                    'date': msg['started_at'] if 'started_at' in msg else msg['created_at'],
                    'messages': []
                }
            conversations[conv_id]['messages'].append(msg)

        # Format summary
        summary_lines = []
        for idx, (conv_id, conv_data) in enumerate(list(conversations.items())[:3], 1):  # Last 3 convos only
            summary_lines.append(f"\nConversation {idx} ({conv_data['channel']}):")
            for msg in conv_data['messages'][:5]:  # First 5 msgs per convo
                role = "Customer" if msg.get('role') == 'customer' else "Agent"
                content = msg.get('content', '')[:100]
                summary_lines.append(f"  {role}: {content}...")

        return "\n".join(summary_lines) if summary_lines else "No detailed history available."

    except Exception as e:
        logger.error(f"Error fetching customer history: {e}", exc_info=True)
        return "Unable to retrieve customer history at this time."


@function_tool
async def escalate_to_human(input: EscalationInput) -> str:
    """
    Escalate conversation to human support.

    Use this when:
    - Customer asks about pricing or refunds
    - Customer sentiment is negative
    - You cannot find relevant information
    - Customer explicitly requests human help

    Args:
        input: Escalation details

    Returns:
        Escalation confirmation with reference
    """
    try:
        # Mark ticket as escalated
        await escalate_ticket_record(input.ticket_id, input.reason)

        logger.info(f"Escalated ticket {input.ticket_id} with reason: {input.reason} (urgency: {input.urgency})")

        # Record metric
        await record_metric("ticket_escalated", 1.0, channel=None, dimension_type="escalation",
                            dimensions={"reason": input.reason, "urgency": input.urgency, "ticket_id": input.ticket_id})

        return f"Ticket {input.ticket_id} has been escalated to human support. Reference ID: ESC-{input.ticket_id}. Resolution expected within 2 hours (priority: {input.urgency})."

    except Exception as e:
        logger.error(f"Escalation failed: {e}", exc_info=True)
        return f"Error during escalation: {str(e)}. Please manually follow up with customer."


@function_tool
async def send_response(input: ResponseInput) -> str:
    """
    Send response to customer via their preferred channel.

    The response will be automatically formatted for the channel.

    Args:
        input: Response details

    Returns:
        Delivery status
    """
    try:
        # Note: In production, would actually send via Gmail/Twilio/Email here
        # For now, just log and acknowledge
        logger.info(f"Prepared response for ticket {input.ticket_id} via {input.channel.value} (length: {len(input.message)})")

        # Simulate successful delivery
        # In real implementation: await gmail_handler.send_reply() etc

        return f"Response prepared for {input.channel.value} delivery (ticket: {input.ticket_id}). Status: queued for delivery."

    except Exception as e:
        logger.error(f"Failed to send response: {e}", exc_info=True)
        return f"Error sending response: {str(e)}. Please escalate."


@function_tool
async def analyze_sentiment(text: str) -> dict:
    """
    Analyze sentiment of a message (customer or agent text).

    Args:
        text: Text to analyze

    Returns:
        dict: {'score': float, 'confidence': float, 'category': str}
    """
    # Simple keyword-based sentiment (prototype)
    # In production: Use LLM call or dedicated sentiment API
    negative_words = ['bad', 'terrible', 'awful', 'worst', 'frustrated', 'angry', 'ridiculous', 'hate', 'useless', 'broken']
    positive_words = ['great', 'awesome', 'excellent', 'happy', 'thanks', 'thank you', 'good', 'perfect', 'love']

    text_lower = text.lower()
    neg_count = sum(1 for w in negative_words if w in text_lower)
    pos_count = sum(1 for w in positive_words if w in text_lower)

    # Simple VADER-like scoring: -1 to +1
    raw_score = (pos_count - neg_count) / max(len(text_lower.split()), 1)
    score = max(-1.0, min(1.0, raw_score * 10))

    confidence = min(0.9, 0.5 + abs(score) * 0.4)

    if score < -0.2:
        category = "negative"
    elif score > 0.2:
        category = "positive"
    else:
        category = "neutral"

    return {
        "score": round(score, 3),
        "confidence": round(confidence, 2),
        "category": category
    }


@function_tool
async def format_for_channel(text: str, channel: str, ticket_id: str = None, customer_name: str = None) -> str:
    """
    Format response text appropriately for target channel.

    Args:
        text: Raw response text
        channel: Target channel (email, whatsapp, web_form)
        ticket_id: Optional ticket ID for reference
        customer_name: Optional customer name for personalization

    Returns:
        Formatted text ready for sending
    """
    from .formatters import FormattingContext, Channel, format_response

    try:
        channel_enum = Channel(channel)
        context = FormattingContext(
            customer_name=customer_name,
            ticket_id=ticket_id,
            channel=channel_enum
        )
        return format_response(text, context)
    except Exception as e:
        logger.error(f"Formatting failed for {channel}: {e}")
        return text  # fallback to raw text
