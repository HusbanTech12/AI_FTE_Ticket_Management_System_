"""
MCP Server: Customer Success FTE (Incubation Phase)

Exposes the incubated agent's capabilities as MCP tools.
This is the bridge between exploration and production.

Tools exposed:
- search_knowledge_base(query) -> relevant docs
- create_ticket(customer_id, issue, priority, channel) -> ticket_id
- get_customer_history(customer_id) -> past interactions across ALL channels
- escalate_to_human(ticket_id, reason) -> escalation_id
- send_response(ticket_id, message, channel) -> delivery_status
- analyze_sentiment(text) -> score, confidence
- format_for_channel(text, channel) -> formatted_text
"""

from enum import Enum
from typing import Optional, Dict, Any
import json
from mcp.server import Server
from mcp.types import Tool, TextContent
import asyncio

# Reuse prototype logic
import sys
sys.path.append('/mnt/d/Quarter_4/Hackathon_5/Ticket_Management_System/incubation/src')
from agent.prototype_agent import CustomerSuccessAgent, Channel, SimpleSearchEngine

# Initialize agent and search engine (lightweight for MCP)
docs_path = "/mnt/d/Quarter_4/Hackathon_5/Ticket_Management_System/context/product-docs.md"
agent = CustomerSuccessAgent(docs_path=docs_path)

# MCP Server
server = Server("customer-success-fte")


class ChannelEnum(str, Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"


@server.tool("search_knowledge_base")
async def search_knowledge_base(query: str, max_results: int = 5) -> list[TextContent]:
    """
    Search product documentation for relevant information.

    Args:
        query: Search query (natural language question)
        max_results: Maximum number of results to return (default: 5)

    Returns:
        List of relevant documentation snippets with titles and relevance scores
    """
    results = agent.search_engine.search(query, max_results=max_results)

    formatted = []
    for r in results:
        formatted.append(
            TextContent(
                type="text",
                text=f"**{r['title']}** (relevance: {r['score']})\n{r['content'][:300]}\n"
            )
        )

    return formatted


@server.tool("create_ticket")
async def create_ticket(
    customer_id: str,
    issue: str,
    priority: str = "medium",
    channel: ChannelEnum = ChannelEnum.EMAIL
) -> TextContent:
    """
    Create a support ticket in the system with channel tracking.

    Args:
        customer_id: Unique customer identifier (email or phone)
        issue: Brief description of the issue/question
        priority: Priority level (low, medium, high)
        channel: Source channel (email, whatsapp, web_form)

    Returns:
        ticket_id: Unique ticket identifier
    """
    # In prototype, store in memory (production uses PostgreSQL)
    import uuid
    ticket_id = str(uuid.uuid4())[:8].upper()

    ticket = {
        "id": ticket_id,
        "customer_id": customer_id,
        "issue": issue,
        "priority": priority,
        "channel": channel.value,
        "created_at": "2025-04-08T00:00:00Z"
    }

    # In prototype, just return ID (would persist in production)
    return TextContent(
        type="text",
        text=f"Ticket created: {ticket_id}\nDetails: {json.dumps(ticket, indent=2)}"
    )


@server.tool("get_customer_history")
async def get_customer_history(customer_id: str) -> TextContent:
    """
    Get customer's interaction history across ALL channels.

    Args:
        customer_id: Customer email or phone number

    Returns:
        JSON-formatted history of past conversations and tickets
    """
    # In prototype, return mock data
    # In production: SELECT * FROM conversations JOIN messages WHERE customer_id = ?
    mock_history = {
        "customer_id": customer_id,
        "total_conversations": 0,
        "channels_used": [],
        "recent_tickets": [],
        "notes": "Prototype returns empty history. Production would query PostgreSQL."
    }
    return TextContent(
        type="text",
        text=f"Customer History for {customer_id}:\n{json.dumps(mock_history, indent=2)}"
    )


@server.tool("escalate_to_human")
async def escalate_to_human(ticket_id: str, reason: str, urgency: str = "normal") -> TextContent:
    """
    Escalate conversation to human support.

    Args:
        ticket_id: The ticket to escalate
        reason: Why escalation is needed
        urgency: Escalation urgency (low, normal, high)

    Returns:
        Escalation confirmation with reference ID
    """
    escalation_id = f"ESC-{ticket_id}"

    # Log escalation (in prototype, just print)
    print(f"[ESCALATION] Ticket {ticket_id} → Human. Reason: {reason}, Urgency: {urgency}")

    return TextContent(
        type="text",
        text=f"Escalated to human support.\nEscalation ID: {escalation_id}\nReason: {reason}\nExpected response time: 2 hours"
    )


@server.tool("send_response")
async def send_response(
    ticket_id: str,
    message: str,
    channel: ChannelEnum
) -> TextContent:
    """
    Send response to customer via the appropriate channel.

    Args:
        ticket_id: The ticket being responded to
        message: Response text (will be formatted for channel)
        channel: Destination channel

    Returns:
        Delivery status and confirmation
    """
    # Format for channel
    formatted = agent.format_response_for_channel(message, Channel(channel.value))

    # In prototype, just validate
    # In production: actually send via Gmail API / Twilio / Email
    return TextContent(
        type="text",
        text=f"Response prepared for ticket {ticket_id}\nChannel: {channel.value}\n"
             f"Length: {len(formatted)} chars\n\n"
             f"Preview:\n{formatted[:200]}..."
    )


@server.tool("analyze_sentiment")
async def analyze_sentiment(text: str) -> TextContent:
    """
    Analyze sentiment of customer message.

    Args:
        text: Message text to analyze

    Returns:
        Sentiment score (-1 to 1, negative to positive) and confidence
    """
    # Simple keyword-based sentiment (prototype)
    negative_words = ["bad", "terrible", "awful", "worst", "frustrated", "angry", "ridiculous"]
    positive_words = ["great", "awesome", "excellent", "happy", "thanks", "good"]

    text_lower = text.lower()
    neg_count = sum(1 for w in negative_words if w in text_lower)
    pos_count = sum(1 for w in positive_words if w in text_lower)

    score = (pos_count - neg_count) / max(len(text_lower.split()), 1) * 10
    confidence = 0.7  # mock confidence

    return TextContent(
        type="text",
        text=f"Sentiment analysis:\n"
             f"Score: {score:.2f} (-1=very negative, +1=very positive)\n"
             f"Confidence: {confidence:.0%}\n"
             f"Interpretation: {'Negative' if score < -0.1 else 'Neutral' if score < 0.3 else 'Positive'}"
    )


@server.tool("format_for_channel")
async def format_for_channel(text: str, channel: ChannelEnum) -> TextContent:
    """
    Format response text appropriately for target channel.

    Args:
        text: Raw response text
        channel: Target channel

    Returns:
        Formatted text ready for sending
    """
    formatted = agent.format_response_for_channel(text, Channel(channel.value))
    return TextContent(
        type="text",
        text=f"Formatted for {channel.value}:\n\n{formatted}"
    )


async def main():
    from mcp import stdio

    async with stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
