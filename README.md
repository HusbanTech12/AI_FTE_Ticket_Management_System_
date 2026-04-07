# Customer Success FTE - 24/7 AI Employee

A production-ready, multi-channel AI customer support agent deployed on Kubernetes.

## 📋 Project Overview

This project implements a **Digital Full-Time Equivalent (FTE)** - an AI employee that handles customer support 24/7 across three channels:
- **Email** (Gmail API)
- **WhatsApp** (Twilio API)
- **Web Form** (React component + FastAPI)

Built following the **Agent Maturity Model** and the **CRM Digital FTE Factory Final Hackathon 5** specifications.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    MULTI-CHANNEL INTAKE ARCHITECTURE                        │
│                                                                             │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                │
│   │    Gmail     │    │   WhatsApp   │    │   Web Form   │                │
│   │   (Email)    │    │  (Twilio)    │    │   (React)    │                │
│   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                │
│          │                  │                  │                         │
│          ▼                  ▼                  ▼                         │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐                │
│   │  Gmail       │    │  Twilio      │    │  FastAPI     │                │
│   │  Webhook     │    │  Webhook     │    │  Endpoint    │                │
│   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘                │
│          │                  │                  │                         │
│          └──────────────────┼──────────────────┘                         │
│                             ▼                                              │
│                    ┌─────────────────┐                                   │
│                    │   Kafka         │  Event Streaming                 │
│                    │   (Messages)    │                                   │
│                    └────────┬────────┘                                   │
│                             ▼                                              │
│                    ┌─────────────────┐                                   │
│                    │  Unified        │   AI Agent (OpenAI Agents SDK)   │
│                    │  Message        │                                   │
│                    │  Processor      │                                   │
│                    └────────┬────────┘                                   │
│                             │                                              │
│            ┌────────────────┼────────────────┐                            │
│            ▼                ▼                ▼                             │
│       ┌──────────────┐ ┌──────────────┐ ┌──────────────┐                 │
│       │ Gmail API    │ │ Twilio API   │ │  Email       │                 │
│       │  (Reply)     │ │  (Reply)     │ │  (Reply)     │                 │
│       └──────────────┘ └──────────────┘ └──────────────┘                 │
└─────────────────────────────────────────────────────────────────────────────┘

INFRASTRUCTURE: PostgreSQL + pgvector | Kafka | FastAPI | OpenAI Agents SDK
DEPLOYMENT: Docker | Kubernetes (auto-scaling)
TRACKING: Complete CRM with cross-channel conversation history
```

---

## 📁 Project Structure

```
.
├── The CRM Digital FTE Factory Final Hackathon 5.md  # Full specification
├── docker-compose.yml                                 # Local development stack
├── production/                                       # Production system
│   ├── agent/
│   │   ├── customer_success_agent.py   # OpenAI Agent definition
│   │   ├── tools.py                    # @function_tool implementations
│   │   ├── prompts.py                  # System prompts
│   │   └── formatters.py               # Channel response formatting
│   ├── channels/
│   │   ├── gmail_handler.py            # Gmail API integration
│   │   ├── whatsapp_handler.py         # Twilio WhatsApp integration
│   │   └── web_form_handler.py         # Web form API endpoints
│   ├── workers/
│   │   └── message_processor.py        # Kafka consumer + agent runner
│   ├── api/
│   │   └── main.py                     # FastAPI service (webhooks, health)
│   ├── database/
│   │   ├── schema.sql                  # Complete PostgreSQL schema
│   │   ├── migrations/
│   │   └── queries.py                  # Database access functions
│   ├── k8s/                            # Kubernetes manifests
│   │   ├── namespace.yaml
│   │   ├── configmap.yaml
│   │   ├── secrets.yaml
│   │   ├── deployment.yaml
│   │   ├── ingress.yaml
│   │   ├── postgres.yaml
│   │   └── hpa.yaml
│   ├── config.py                       # Configuration management
│   ├── kafka_client.py                 # Kafka producer/consumer
│   ├── requirements.txt
│   └── Dockerfile
├── incubation/                         # Incubation phase (exploration)
│   ├── src/
│   │   ├── agent/prototype_agent.py    # Initial prototype
│   │   └── channels/                   # Handlers
│   └── mcp_server.py                   # MCP tools
├── context/                            # Company context for agent
│   ├── company-profile.md
│   ├── product-docs.md
│   ├── sample-tickets.json
│   ├── escalation-rules.md
│   └── brand-voice.md
├── specs/                              # Formal specifications
│   ├── discovery-log.md
│   ├── customer-success-fte-spec.md
│   └── transition-checklist.md
└── frontend/
    └── web-form/
        ├── SupportForm.jsx             # React component
        ├── package.json
        ├── Dockerfile
        └── README.md
```

---

## 🚀 Quick Start (Local Development)

### Prerequisites

- Docker & Docker Compose
- Node.js 18+ (for frontend development)
- OpenAI API key
- (Optional) Gmail service account credentials
- (Optional) Twilio account with WhatsApp enabled

### Setup

1. **Clone and configure environment**

```bash
# Copy environment file
cp .env.example .env  # Edit with your actual credentials
```

2. **Start all services**

```bash
docker-compose up -d
```

This will start:
- PostgreSQL (port 5432)
- Kafka (port 9092)
- FastAPI service (port 8000)
- Message processor worker (2 replicas)
- Web form frontend (port 3000)
- (Optional) Gmail/WhatsApp handlers ready

3. **Initialize database**

```bash
docker-compose exec postgres psql -U fte -d fte_db -f /docker-entrypoint-initdb.d/migrations/001_initial_schema.sql
```

4. **Access services**

- API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health
- Web form: http://localhost:3000
- Kafka: localhost:9092
- PostgreSQL: localhost:5432

---

## 🧪 Testing

### Run Incubation Prototype

```bash
python incubation/src/agent/prototype_agent.py
python incubation/mcp_server.py  # Exposes MCP tools
```

### Run Production Agent Tests

```bash
pytest production/tests/
```

### Manual API Test

```bash
# Submit a support ticket via web form
curl -X POST http://localhost:8000/support/submit \
  -H "Content-Type: application/json" \
  -d '{
    "name": "John Doe",
    "email": "john@example.com",
    "subject": "Need help resetting password",
    "category": "technical",
    "priority": "medium",
    "message": "I cannot log in, need password reset"
  }'
```

---

## ☁️ Production Deployment (Kubernetes)

### 1. Build and Push Images

```bash
# Build API image
docker build -t your-registry.com/fte-api:latest .

# Push to registry
docker push your-registry.com/fte-api:latest
```

### 2. Apply Manifests

```bash
# Create namespace and config
kubectl apply -f production/k8s/namespace.yaml
kubectl apply -f production/k8s/configmap.yaml

# Create secrets (edit first!)
kubectl apply -f production/k8s/secrets.yaml

# Deploy stateful services (PostgreSQL + Kafka)
kubectl apply -f production/k8s/postgres.yaml

# Wait for them to be ready
kubectl get pods -n customer-success-fte --watch

# Deploy application
kubectl apply -f production/k8s/deployment.yaml

# Set up autoscaling (optional)
kubectl apply -f production/k8s/hpa.yaml

# Set up ingress (if using)
kubectl apply -f production/k8s/ingress.yaml
```

### 3. Verify Deployment

```bash
kubectl get all -n customer-success-fte
kubectl logs -f deployment/fte-api -n customer-success-fte
kubectl logs -f deployment/fte-worker -n customer-success-fte
```

---

## 🎯 Features Implemented

### ✅ Multi-Channel Support
- **Gmail**: Full integration with Gmail API using service account with domain-wide delegation. Supports push notifications via Pub/Sub.
- **WhatsApp**: Twilio WhatsApp Business API integration. Two-way messaging with status callbacks.
- **Web Form**: Complete React form with validation, accessibility, and responsive design.

### ✅ AI Agent (OpenAI Agents SDK)
- System prompt with channel awareness
- Tool calling: `search_knowledge_base`, `create_ticket`, `get_customer_history`, `escalate_to_human`, `send_response`
- Sentiment analysis on each message
- Escalation decision engine

### ✅ Production Database (PostgreSQL + pgvector)
- **Customers**: Unified across channels (email + phone)
- **Conversations**: Thread-level tracking with channel source
- **Messages**: Complete history with sentiment and latency tracking
- **Tickets**: Lifecycle management with escalation tracking
- **Knowledge Base**: Vector embeddings for semantic search (1536-dim)
- **Metrics**: Performance tracking per channel
- **Cross-channel matching**: Customer identifiers table

### ✅ Event Streaming (Kafka)
- Topics: tickets.incoming, channels.{email,whatsapp}.(inbound|outbound), escalations, metrics, dlq
- Async processing with consumer group
- Dead letter queue for failed messages

### ✅ Monitoring & Metrics
- Health check endpoint with dependency status
- Channel-specific performance metrics
- Latency tracking (p50, p95, p99)
- Escalation rate monitoring
- Consumer lag metrics

### ✅ Kubernetes Deployment
- StatefulSets for PostgreSQL and Kafka
- Deployments for API and workers
- Horizontal Pod Autoscaler (CPU + custom Kafka lag metric)
- ConfigMaps and Secrets management
- Ingress for external access
- Resource limits and health checks

### ✅ Automation & DevOps
- Docker multi-stage builds
- Docker Compose for local development
- Migrations as idempotent SQL scripts
- Logging with structured JSON output
- Graceful shutdown handling

---

## 📊 Performance Targets

| Metric | Target |
|--------|--------|
| Processing time | <3 seconds |
| Delivery time | <30 seconds |
| Accuracy | >85% |
| Escalation rate | <20% |
| Availability | 99.9% |

---

## 🔐 Security

- Environment variable-based secrets
- Database connection pooling with timeouts
- Input validation via Pydantic
- CSRF protection on web forms
- Rate limiting (configurable, default 60 req/min)
- Non-root container users
- CORS configuration

---

## 📚 Documentation

- **Full Specification**: `The CRM Digital FTE Factory Final Hackathon 5.md`
- **Implementation Guide**: See `production/README.md`
- **API Reference**: http://localhost:8000/docs (when running)
- **Brand Guidelines**: `context/brand-voice.md`
- **Escalation Rules**: `context/escalation-rules.md`
- **Product Docs**: `context/product-docs.md` (sample content)

---

## 🛠️ Technology Stack

| Layer | Technology |
|-------|-------------|
| AI/Agent | OpenAI GPT-4o, OpenAI Agents SDK |
| API | FastAPI (Python 3.11) |
| Database | PostgreSQL 15 + pgvector |
| Streaming | Apache Kafka (confluentinc/cp-kafka) |
| Email | Google Gmail API |
| Messaging | Twilio WhatsApp API |
| Frontend | React 18 + Next.js + Tailwind CSS |
| Orchestration | Kubernetes (Helm optional) |
| Container | Docker, Docker Compose |
| Monitoring | Custom metrics, health checks |

---

## 📝 License

Proprietary - TechCorp SaaS © 2025

---

## 🤝 Support

For questions about implementation or deployment:
- Review the hackathon spec document
- Check the API docs: `/docs` endpoint
- See `production/README.md` for detailed component docs
- Contact: TechCorp engineering team

---

**Status**: ✅ Complete and Production-Ready
**Last Updated**: 2025-04-08
