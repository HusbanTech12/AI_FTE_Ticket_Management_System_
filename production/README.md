# Production System - Customer Success FTE

## Directory Structure

```
production/
├── agent/
│   ├── __init__.py
│   ├── customer_success_agent.py   # Agent definition with OpenAI SDK
│   ├── tools.py                    # @function_tool definitions
│   ├── prompts.py                  # System prompts
│   └── formatters.py               # Channel response formatting
├── channels/
│   ├── __init__.py
│   ├── gmail_handler.py            # Gmail API integration
│   ├── whatsapp_handler.py         # Twilio WhatsApp integration
│   └── web_form_handler.py         # Web form endpoints
├── workers/
│   ├── __init__.py
│   ├── message_processor.py        # Kafka consumer + agent runner
│   └── metrics_collector.py        # Background metrics collection
├── api/
│   ├── __init__.py
│   └── main.py                     # FastAPI application with webhooks
├── database/
│   ├── __init__.py
│   ├── schema.sql                  # PostgreSQL DDL
│   ├── migrations/
│   │   └── 001_initial_schema.sql
│   └── queries.py                  # Database access functions
├── k8s/                            # Kubernetes manifests
├── tests/
│   ├── __init__.py
│   ├── test_agent.py
│   ├── test_channels.py
│   └── test_e2e.py
├── config.py                       # Centralized configuration
├── Dockerfile
├── requirements.txt
└── docker-compose.yml              # Local development stack

frontend/
└── web-form/
    ├── SupportForm.jsx
    ├── package.json
    └── README.md
```

## Local Development

```bash
# Start all services (PostgreSQL, Kafka, API, Workers)
docker-compose up -d

# Run tests
pytest production/tests/

# View logs
docker-compose logs -f fte-api
```

## Deploy to Kubernetes

```bash
# Build and push images
docker build -t your-registry/fte-api:latest .
docker push your-registry/fte-api:latest

# Apply Kubernetes manifests
kubectl apply -f production/k8s/

# Check status
kubectl get pods -n customer-success-fte
```

## Environment Variables

See `production/config.py` for full list. Key variables:

- `DATABASE_URL`: PostgreSQL connection string
- `KAFKA_BOOTSTRAP_SERVERS`: Kafka brokers
- `OPENAI_API_KEY`: OpenAI API key
- `GMAIL_CREDENTIALS_PATH`: Path to Gmail service account JSON
- `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_NUMBER`: Twilio config
