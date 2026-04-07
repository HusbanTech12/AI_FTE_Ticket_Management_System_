-- =============================================================================
-- CUSTOMER SUCCESS FTE CRM/TICKET MANAGEMENT SYSTEM
-- =============================================================================
-- PostgreSQL schema serving as complete CRM system with multi-channel support:
-- - Customer unification across channels
-- - Conversation threading and message history
-- - Ticket lifecycle with channel tracking
-- - Knowledge base for AI responses (with pgvector)
-- - Performance metrics and reporting
-- =============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";  -- pgvector for semantic search
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- CORE TABLES
-- =============================================================================

-- Customers (unified across channels)
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255),
    phone VARCHAR(50),
    name VARCHAR(255),
    company VARCHAR(255),
    tier VARCHAR(20) DEFAULT 'starter',  -- starter, professional, enterprise
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    UNIQUE(email),
    UNIQUE(phone)
);

-- Customer identifiers for cross-channel matching
CREATE TABLE customer_identifiers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID REFERENCES customers(id) ON DELETE CASCADE,
    identifier_type VARCHAR(50) NOT NULL,  -- 'email', 'phone', 'whatsapp'
    identifier_value VARCHAR(255) NOT NULL,
    verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(identifier_type, identifier_value)
);
CREATE INDEX idx_customer_identifiers_customer ON customer_identifiers(customer_id);
CREATE INDEX idx_customer_identifiers_value ON customer_identifiers(identifier_value);

-- Conversations (session-level, can span multiple tickets)
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
    initial_channel VARCHAR(50) NOT NULL,  -- 'email', 'whatsapp', 'web_form'
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    ended_at TIMESTAMP WITH TIME ZONE,
    status VARCHAR(50) DEFAULT 'active',  -- active, closed, escalated
    sentiment_score DECIMAL(3,2),
    resolution_type VARCHAR(50),  -- ai_resolved, escalated, abandoned
    escalated_to VARCHAR(255),
    subject TEXT,
    metadata JSONB DEFAULT '{}'
);
CREATE INDEX idx_conversations_customer ON conversations(customer_id);
CREATE INDEX idx_conversations_status ON conversations(status);
CREATE INDEX idx_conversations_channel ON conversations(initial_channel);
CREATE INDEX idx_conversations_started ON conversations(started_at DESC);

-- Messages (individual communications within conversations)
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    channel VARCHAR(50) NOT NULL,  -- 'email', 'whatsapp', 'web_form'
    direction VARCHAR(20) NOT NULL,  -- 'inbound', 'outbound'
    role VARCHAR(20) NOT NULL,  -- 'customer', 'agent', 'system'
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    tokens_used INTEGER,
    latency_ms INTEGER,  -- Processing time in milliseconds
    tool_calls JSONB DEFAULT '[]',  -- Array of tool call records
    channel_message_id VARCHAR(255),  -- External: Gmail message ID, Twilio SID
    delivery_status VARCHAR(50) DEFAULT 'pending',  -- pending, sent, delivered, failed
    sentiment_score DECIMAL(3,2),
    metadata JSONB DEFAULT '{}'
);
CREATE INDEX idx_messages_conversation ON messages(conversation_id);
CREATE INDEX idx_messages_channel ON messages(channel);
CREATE INDEX idx_messages_created ON messages(created_at DESC);
CREATE INDEX idx_messages_direction ON messages(direction);

-- Tickets (formal support requests)
CREATE TABLE tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
    source_channel VARCHAR(50) NOT NULL,  -- 'email', 'whatsapp', 'web_form'
    category VARCHAR(100),  -- 'general', 'technical', 'billing', 'feedback', 'bug_report'
    priority VARCHAR(20) DEFAULT 'medium',  -- low, medium, high
    status VARCHAR(50) DEFAULT 'open',  -- open, in_progress, resolved, escalated, closed
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_notes TEXT,
    escalation_reason TEXT,
    subject TEXT NOT NULL,
    metadata JSONB DEFAULT '{}'
);
CREATE INDEX idx_tickets_customer ON tickets(customer_id);
CREATE INDEX idx_tickets_status ON tickets(status);
CREATE INDEX idx_tickets_channel ON tickets(source_channel);
CREATE INDEX idx_tickets_created ON tickets(created_at DESC);
CREATE INDEX idx_tickets_category ON tickets(category);

-- Knowledge base (product documentation with vector embeddings)
CREATE TABLE knowledge_base (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(100),  -- 'getting_started', 'features', 'integrations', 'billing', 'troubleshooting'
    tags TEXT[] DEFAULT '{}',
    embedding vector(1536),  -- OpenAI text-embedding-3-small produces 1536-dim vectors
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);
CREATE INDEX idx_knowledge_category ON knowledge_base(category);
CREATE INDEX idx_knowledge_embedding ON knowledge_base USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_knowledge_title ON knowledge_base(title);

-- Channel configurations (per-channel settings)
CREATE TABLE channel_configs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    channel VARCHAR(50) UNIQUE NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    config JSONB NOT NULL,  -- API keys, webhook URLs, rate limits
    response_template TEXT,
    max_response_length INTEGER,
    rate_limit_per_minute INTEGER DEFAULT 60,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Agent performance metrics
CREATE TABLE agent_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(10,4) NOT NULL,
    channel VARCHAR(50),  -- Optional: channel-specific metrics
    dimension_type VARCHAR(50),  -- 'ticket_count', 'response_time', 'sentiment_avg', etc.
    dimensions JSONB DEFAULT '{}',
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_agent_metrics_name ON agent_metrics(metric_name);
CREATE INDEX idx_agent_metrics_recorded ON agent_metrics(recorded_at DESC);
CREATE INDEX idx_agent_metrics_channel ON agent_metrics(channel);

-- =============================================================================
-- VIEWS (for reporting and dashboards)
-- =============================================================================

-- Customer conversation summary
CREATE VIEW customer_summaries AS
SELECT
    c.id AS customer_id,
    c.email,
    c.name,
    c.tier,
    COUNT(DISTINCT conv.id) AS total_conversations,
    COUNT(DISTINCT t.id) AS total_tickets,
    COUNT(DISTINCT t.id) FILTER (WHERE t.status = 'escalated') AS escalated_tickets,
    AVG(conv.sentiment_score) AS avg_sentiment,
    MAX(conv.started_at) AS last_contacted,
    COUNT(DISTINCT conv.initial_channel) AS channels_used
FROM customers c
LEFT JOIN conversations conv ON conv.customer_id = c.id
LEFT JOIN tickets t ON t.customer_id = c.id
GROUP BY c.id, c.email, c.name, c.tier;

-- Daily performance dashboard
CREATE VIEW daily_performance AS
SELECT
    DATE(m.created_at) AS day,
    m.channel,
    COUNT(*) FILTER (WHERE m.direction = 'inbound') AS inbound_messages,
    COUNT(*) FILTER (WHERE m.direction = 'outbound' AND m.role = 'agent') AS agent_responses,
    AVG(m.latency_ms) AS avg_response_latency_ms,
    COUNT(DISTINCT t.id) AS tickets_created,
    COUNT(DISTINCT t.id) FILTER (WHERE t.status = 'escalated') AS escalations,
    AVG(m.sentiment_score) AS avg_sentiment
FROM messages m
LEFT JOIN conversations conv ON conv.id = m.conversation_id
LEFT JOIN tickets t ON t.conversation_id = conv.id
GROUP BY DATE(m.created_at), m.channel
ORDER BY day DESC, channel;

-- =============================================================================
-- FUNCTIONS
-- =============================================================================

-- Update updated_at timestamp trigger function
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply updated_at triggers
CREATE TRIGGER trg_customers_updated_at
    BEFORE UPDATE ON customers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_channel_configs_updated_at
    BEFORE UPDATE ON channel_configs
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- =============================================================================
-- SEED DATA
-- =============================================================================

-- Seed channel configurations
INSERT INTO channel_configs (channel, enabled, config, max_response_length) VALUES
    ('email', true, '{"smtp_from": "support@flowsync.com", "reply_to": "support@flowsync.com"}', 3000),
    ('whatsapp', true, '{"twilio_from": "whatsapp:+14155238886"}', 1600),
    ('web_form', true, '{"auto_reply": true, "auto_reply_email": true}', 1800)
ON CONFLICT (channel) DO NOTHING;

-- Seed test customer
INSERT INTO customers (email, name, tier) VALUES
    ('alice@example.com', 'Alice Johnson', 'starter')
ON CONFLICT (email) DO NOTHING;

-- =============================================================================
-- INDEXES FOR COMMON QUERIES
-- =============================================================================

-- Customer resolution by email
CREATE INDEX idx_customers_email_lookup ON customers(email) WHERE email IS NOT NULL;

-- Active conversations for customer
CREATE INDEX idx_conversations_active ON conversations(customer_id, status)
    WHERE status = 'active';

-- Open tickets by source
CREATE INDEX idx_tickets_open ON tickets(status, source_channel)
    WHERE status IN ('open', 'in_progress');
