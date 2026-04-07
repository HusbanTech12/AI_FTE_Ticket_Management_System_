"""
Database access functions for Customer Success FTE.

Uses asyncpg for async PostgreSQL connectivity with connection pooling.
All queries are parameterized (safe from SQL injection).
"""

import asyncpg
import json
from typing import Optional, List, Dict, Any
from typing import Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class Channel(str, Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"


class TicketStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    CLOSED = "closed"


class ConversationStatus(str, Enum):
    ACTIVE = "active"
    CLOSED = "closed"
    ESCALATED = "escalated"


@dataclass
class CustomerRecord:
    id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    name: Optional[str] = None
    tier: str = "starter"
    metadata: dict = None


@dataclass
class TicketRecord:
    id: str
    conversation_id: str
    customer_id: str
    source_channel: str
    category: Optional[str] = None
    priority: str = "medium"
    status: str = "open"
    subject: str = ""
    created_at: str = ""
    escalation_reason: Optional[str] = None


@dataclass
class MessageRecord:
    id: str
    conversation_id: str
    channel: str
    direction: str
    role: str
    content: str
    created_at: str
    latency_ms: int = None
    sentiment_score: float = None
    metadata: dict = None


class DatabasePool:
    """Singleton-style connection pool. In production, use dependency injection."""
    _pool = None

    @classmethod
    async def get_pool(cls, dsn: str) -> asyncpg.Pool:
        if cls._pool is None:
            cls._pool = await asyncpg.create_pool(
                dsn,
                min_size=2,
                max_size=10,
                max_inactive_time=300,
                command_timeout=10  # 10s timeout
            )
            logger.info("Connection pool created")
        return cls._pool

    @classmethod
    async def close(cls):
        if cls._pool:
            await cls._pool.close()
            cls._pool = None


async def get_pool(dsn: str = None) -> asyncpg.Pool:
    """Get or create database connection pool."""
    import os
    dsn = dsn or os.getenv("DATABASE_URL", "postgresql://fte:fte_password@localhost:5432/fte_db")
    return await DatabasePool.get_pool(dsn)


# =============================================================================
# CUSTOMER QUERIES
# =============================================================================

async def resolve_or_create_customer(
    email: str = None,
    phone: str = None,
    name: str = None
) -> str:
    """
    Find existing customer by email or phone, or create new one.
    Returns customer UUID.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Try email
        if email:
            customer = await conn.fetchrow(
                "SELECT id FROM customers WHERE email = $1", email
            )
            if customer:
                return str(customer['id'])

            # Create new customer with email
            customer_id = await conn.fetchval(
                "INSERT INTO customers (email, name) VALUES ($1, $2) RETURNING id",
                email, name or ""
            )
            await conn.execute(
                """INSERT INTO customer_identifiers (customer_id, identifier_type, identifier_value, verified)
                   VALUES ($1, 'email', $2, TRUE)
                   ON CONFLICT (identifier_type, identifier_value) DO NOTHING""",
                customer_id, email
            )
            return str(customer_id)

        # Try phone (WhatsApp)
        if phone:
            identifier = await conn.fetchrow(
                """SELECT customer_id FROM customer_identifiers
                   WHERE identifier_type IN ('phone', 'whatsapp') AND identifier_value = $1""",
                phone
            )
            if identifier:
                return str(identifier['customer_id'])

            # Create new customer with phone
            customer_id = await conn.fetchval(
                "INSERT INTO customers (phone) VALUES ($1) RETURNING id",
                phone
            )
            await conn.execute(
                """INSERT INTO customer_identifiers (customer_id, identifier_type, identifier_value, verified)
                   VALUES ($1, 'whatsapp', $2, FALSE)
                   ON CONFLICT (identifier_type, identifier_value) DO NOTHING""",
                customer_id, phone
            )
            return str(customer_id)

    raise ValueError("Must provide email or phone to resolve/create customer")


async def get_customer(customer_id: str) -> Optional[CustomerRecord]:
    """Look up customer by ID, including all identifiers."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        customer = await conn.fetchrow("SELECT * FROM customers WHERE id = $1", customer_id)
        if not customer:
            return None

        identifiers = await conn.fetch(
            "SELECT identifier_type, identifier_value FROM customer_identifiers WHERE customer_id = $1",
            customer_id
        )

        return CustomerRecord(
            id=str(customer['id']),
            email=customer.get('email'),
            phone=customer.get('phone'),
            name=customer.get('name'),
            tier=customer.get('tier', 'starter'),
            metadata=dict(customer.get('metadata', {})),
        )


async def get_customer_history(customer_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Get customer's interaction history across ALL channels."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT c.id AS conversation_id, c.initial_channel, c.started_at, c.status,
                   c.sentiment_score, c.resolution_type,
                   m.id AS message_id, m.channel, m.direction, m.role, m.content,
                   m.created_at, m.sentiment_score AS message_sentiment
            FROM conversations c
            JOIN messages m ON m.conversation_id = c.id
            WHERE c.customer_id = $1
            ORDER BY m.created_at DESC
            LIMIT $2
        """, customer_id, limit)

        return [dict(r) for r in rows]


# =============================================================================
# CONVERSATION QUERIES
# =============================================================================

async def get_or_create_conversation(
    customer_id: str,
    channel: Channel,
    subject: str = None
) -> str:
    """Find active conversation (last 24 hours) or create new one."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Check for active conversation (within last 24 hours)
        active = await conn.fetchrow("""
            SELECT id FROM conversations
            WHERE customer_id = $1
              AND status = 'active'
              AND started_at > NOW() - INTERVAL '24 hours'
            ORDER BY started_at DESC
            LIMIT 1
        """, customer_id)

        if active:
            return str(active['id'])

        # Create new conversation
        conversation_id = await conn.fetchval("""
            INSERT INTO conversations (customer_id, initial_channel, status, subject)
            VALUES ($1, $2, 'active', $3)
            RETURNING id
        """, customer_id, channel.value, subject)

        return str(conversation_id)


async def close_conversation(conversation_id: str, resolution_type: str = "ai_resolved"):
    """Mark conversation as closed."""
    pool = await get_pool()
    async with pool.acquires() as conn:
        await conn.execute("""
            UPDATE conversations
            SET status = 'closed', ended_at = NOW(), resolution_type = $2
            WHERE id = $1
        """, conversation_id, resolution_type)


# =============================================================================
# MESSAGE QUERIES
# =============================================================================

async def store_message(
    conversation_id: str,
    channel: Channel,
    direction: str,  # 'inbound' or 'outbound'
    role: str,  # 'customer', 'agent', 'system'
    content: str,
    channel_message_id: str = None,
    tokens_used: int = None,
    latency_ms: int = None,
    tool_calls: list = None,
    sentiment_score: float = None
) -> str:
    """Store a message in the database."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        message_id = await conn.fetchval("""
            INSERT INTO messages
                (conversation_id, channel, direction, role, content,
                 channel_message_id, tokens_used, latency_ms, tool_calls, sentiment_score)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING id
        """, conversation_id, channel.value, direction, role, content,
             channel_message_id, tokens_used, latency_ms,
             json.dumps(tool_calls) if tool_calls else '[]', sentiment_score)
        return str(message_id)


async def get_conversation_messages(conversation_id: str, limit: int = 20) -> List[Dict]:
    """Get recent messages for a conversation (for agent context)."""
    pool = await get_pool()
    async with pool.acquires() as conn:
        messages = await conn.fetch("""
            SELECT id, channel, direction, role, content, created_at,
                   latency_ms, tool_calls, sentiment_score
            FROM messages
            WHERE conversation_id = $1
            ORDER BY created_at DESC
            LIMIT $2
        """, conversation_id, limit)

        # Return in chronological order (oldest first)
        return [dict(m) for m in reversed(messages)]


# =============================================================================
# TICKET QUERIES
# =============================================================================

async def create_ticket(
    conversation_id: str,
    customer_id: str,
    source_channel: Channel,
    subject: str,
    category: str = "general",
    priority: str = "medium"
) -> str:
    """Create a support ticket."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        ticket_id = await conn.fetchval("""
            INSERT INTO tickets (conversation_id, customer_id, source_channel, subject, category, priority, status)
            VALUES ($1, $2, $3, $4, $5, $6, 'open')
            RETURNING id
        """, conversation_id, customer_id, source_channel.value, subject, category, priority)
        return str(ticket_id)


async def escalate_ticket(ticket_id: str, reason: str):
    """Escalate a ticket to human support."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE tickets
            SET status = 'escalated', escalation_reason = $2
            WHERE id = $1
        """, ticket_id, reason)


async def resolve_ticket(ticket_id: str, notes: str = None):
    """Mark a ticket as resolved."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE tickets
            SET status = 'resolved', resolved_at = NOW(), resolution_notes = $2
            WHERE id = $1
        """, ticket_id, notes or "")


# =============================================================================
# KNOWLEDGE BASE QUERIES
# =============================================================================

async def search_knowledge_base(query: str, query_embedding: list, max_results: int = 5, category: str = None) -> List[Dict]:
    """Search knowledge base using vector similarity."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        if category:
            results = await conn.fetch("""
                SELECT title, content, category, tags,
                       1 - (embedding <=> $1::vector) as similarity
                FROM knowledge_base
                WHERE is_active = TRUE
                  AND category = $3
                ORDER BY embedding <=> $1::vector
                LIMIT $2
            """, query_embedding, max_results, category)
        else:
            results = await conn.fetch("""
                SELECT title, content, category, tags,
                       1 - (embedding <=> $1::vector) as similarity
                FROM knowledge_base
                WHERE is_active = TRUE
                ORDER BY embedding <=> $1::vector
                LIMIT $2
            """, query_embedding, max_results)

        return [dict(r) for r in results]


# =============================================================================
# METRICS QUERIES
# =============================================================================

async def record_metric(metric_name: str, metric_value: float, channel: str = None, dimension_type: str = None, dimensions: dict = None):
    """Record a metric value for tracking."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO agent_metrics (metric_name, metric_value, channel, dimension_type, dimensions)
            VALUES ($1, $2, $3, $4, $5)
        """, metric_name, metric_value, channel, dimension_type, json.dumps(dimensions or {}))
