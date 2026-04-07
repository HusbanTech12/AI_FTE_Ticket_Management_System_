"""
Customer Success FTE Agent - Production Implementation

Uses OpenAI Agents SDK to create a production-ready AI agent with multi-channel support.

This agent:
- Handles incoming messages from Email, WhatsApp, and Web Form
- Uses tools to interact with database (create_ticket, search_knowledge_base, etc.)
- Formats responses appropriately for each channel
- Decides when to escalate
- Maintains conversation context
"""

import os
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from agents import Agent, Runner, function_tool
from pydantic import BaseModel, Field

from .prompts import CUSTOMER_SUCCESS_SYSTEM_PROMPT
from .tools import (
    search_knowledge_base,
    create_ticket,
    get_customer_history,
    escalate_to_human,
    send_response,
    analyze_sentiment,
    format_for_channel,
    DBChannel
)
from .formatters import Channel, FormattingContext

logger = logging.getLogger(__name__)


class AgentResponse(BaseModel):
    """Structured response from the agent."""
    output: str = Field(..., description="Agent's response text to send to customer")
    escalated: bool = Field(False, description="Whether conversation was escalated")
    escalation_reason: Optional[str] = Field(None, description="Reason for escalation, if any")
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list, description="Tools called during execution")
    sentiment: Optional[float] = Field(None, description="Detected customer sentiment")
    processing_time_ms: float = Field(0.0, description="Total processing time")
    channel: str = Field("", description="Channel response intended for")


# Define the agent with strict tool usage rules
customer_success_agent = Agent(
    name="Customer Success FTE",
    model="gpt-4o",  # or gpt-4-turbo
    instructions=CUSTOMER_SUCCESS_SYSTEM_PROMPT,
    tools=[
        search_knowledge_base,
        create_ticket,
        get_customer_history,
        escalate_to_human,
        send_response,
        analyze_sentiment,
        format_for_channel
    ],
    # In production, we might use output_type=AgentResponse for structured outputs
)


async def run_agent(
    message: str,
    channel: str,
    customer_id: str = None,
    conversation_id: str = None,
    subject: str = None,
    customer_name: str = None,
    metadata: Optional[Dict[str, Any]] = None
) -> AgentResponse:
    """
    Run the agent for a single customer message.

    This is the main entry point for the message processor worker.

    Args:
        message: Customer's message text
        channel: Source channel (email, whatsapp, web_form)
        customer_id: Customer identifier (email or phone)
        conversation_id: Existing conversation ID (if continuing)
        subject: Message subject (email only)
        customer_name: Customer name if known
        metadata: Additional context (channel message ID, etc.)

    Returns:
        AgentResponse with output, escalation decision, and metrics
    """
    start_time = datetime.utcnow()
    ticket_id = None
    formatted_response = None
    escalated = False
    escalation_reason = None

    logger.info(f"Processing {channel} message from {customer_id or 'unknown'}: {message[:50]}...")

    try:
        # Build conversation context
        # Note: OpenAI Agents SDK handles conversation history via messages array
        # For multi-turn, we'll store messages in DB and retrieve history

        messages = []

        # System prompt is already baked into agent definition
        # Add user message
        messages.append({
            "role": "user",
            "content": message
        })

        # Build context dictionary for agent
        context = {
            "channel": channel,
            "customer_id": customer_id,
            "conversation_id": conversation_id,
            "subject": subject,
            "customer_name": customer_name,
            "metadata": metadata or {}
        }

        # Run agent
        result = await Runner.run(
            customer_success_agent,
            messages=messages,
            context=context
        )

        # Extract tool calls for audit
        tool_calls = []
        if hasattr(result, 'tool_calls') and result.tool_calls:
            for tc in result.tool_calls:
                tool_calls.append({
                    "tool": tc.get('name', 'unknown'),
                    "parameters": tc.get('parameters', {}) if hasattr(tc, 'get') else {},
                    "result": tc.get('result', {}) if hasattr(tc, 'get') else {}
                })

        # Detect if escalation happened (agent would have called escalate_to_human)
        escalated = any(tc.get('name') == 'escalate_to_human' for tc in tool_calls)

        # Format response for channel if not escalated
        if not escalated:
            try:
                formatted_response = await format_for_channel(
                    text=result.final_output,
                    channel=channel,
                    ticket_id=ticket_id,
                    customer_name=customer_name
                )
            except Exception as e:
                logger.error(f"Failed to format response: {e}")
                formatted_response = result.final_output

        # Calculate processing time
        processing_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        logger.info(f"Agent processed in {processing_time_ms:.0f}ms, escalated={escalated}")

        return AgentResponse(
            output=formatted_response or result.final_output,
            escalated=escalated,
            escalation_reason=escalation_reason,
            tool_calls=tool_calls,
            sentiment=None,  # Would be extracted from analysis
            processing_time_ms=processing_time_ms,
            channel=channel
        )

    except Exception as e:
        logger.error(f"Agent execution failed: {e}", exc_info=True)
        processing_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000

        return AgentResponse(
            output="I apologize, but I'm experiencing technical difficulties. I'll escalate this to a human agent who will assist you shortly.",
            escalated=True,
            escalation_reason=f"Agent error: {str(e)}",
            tool_calls=[],
            processing_time_ms=processing_time_ms,
            channel=channel
        )


# ============================================================================
# TESTING (for incubation phase and CI)
# ============================================================================

async def test_agent():
    """Quick test of the agent for incubation verification."""
    test_cases = [
        {
            "message": "How do I reset my password?",
            "channel": "email",
            "customer": "test@example.com"
        },
        {
            "message": "I need help with billing, I was charged twice",
            "channel": "whatsapp",
            "customer": "+15551234567"
        }
    ]

    for test in test_cases:
        print(f"\n--- Testing {test['channel']}: {test['message'][:50]} ---")
        response = await run_agent(
            message=test['message'],
            channel=test['channel'],
            customer_id=test['customer']
        )
        print(f"Escalated: {response.escalated}")
        print(f"Response: {response.output[:150]}{'...' if len(response.output) > 150 else ''}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_agent())
