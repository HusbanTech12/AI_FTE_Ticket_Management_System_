# Transition Checklist: General Agent → Custom Agent

## 1. Discovered Requirements

### From Incubation Phase

- [x] Requirement 1: Multi-channel intake system (Email/Gmail, WhatsApp/Twilio, Web Form)
- [x] Requirement 2: Customer unification across channels (email/phone matching)
- [x] Requirement 3: Knowledge base semantic search (pgvector embeddings)
- [x] Requirement 4: Ticket lifecycle tracking with channel metadata
- [x] Requirement 5: Escalation decision engine (rule-based + LLM detection)
- [x] Requirement 6: Channel-specific response formatting (formal/concise/semi-formal)
- [x] Requirement 7: Sentiment analysis on every inbound message
- [x] Requirement 8: Cross-channel conversation continuity (history spanning multiple channels)
- [x] Requirement 9: Asynchronous message processing via Kafka
- [x] Requirement 10: Metrics tracking per channel (latency, escalation rate, CSAT)

## 2. Working Prompts

### System Prompt That Worked:
See `production/agent/prompts.py` for the exact production system prompt. Key elements discovered:
- Channel awareness instructions
- Hard constraints (NEVER discuss pricing, NEVER promise features)
- Escalation triggers (keywords, sentiment thresholds)
- Response quality standards (concise, accurate, empathetic, actionable)

### Tool Descriptions That Worked:
All tool descriptions in `production/agent/tools.py` contain detailed docstrings for LLM consumption, including:
- When to use the tool
- Required/optional parameters
- Expected output format

## 3. Edge Cases Found During Incubation

| Edge Case | How It Was Handled | Test Case Needed |
|-----------|-------------------|------------------|
| Empty message | Ask for clarification | Yes |
| Pricing inquiry | Escalate immediately with reason "pricing_inquiry" | Yes |
| Billing question | Escalate (sensitive financial data) | Yes |
| Feature request | Escalate, log for product team | Yes |
| Angry customer (sentiment < 0.3) | Show empathy, then escalate | Yes |
| Cross-channel continuity | Unified customer record, history retrieval | Yes |
| Very long WhatsApp (>1000 chars) | Split at sentence boundaries | Yes |
| No results from KB after 2 searches | Escalate to human | Yes |
| "Speak to human" keyword | Escalate immediately | Yes |
| Message with attachments | Extract text, note attachments in metadata | Yes |
| Duplicate customer (email + phone) | Unified via customer_identifiers table | Yes |
| Customer switches channel mid-conversation | Detect via customer ID, load cross-channel history | Yes |
| Technical error processing message | Send apology, publish to DLQ, escalate to human | Yes |
| Rate limiting (too many messages) | Log warning, reject if over quota | Yes |
| Multi-language message | Detect, if not supported → escalate | Yes |

## 4. Response Patterns

### Email
- **Format**: Formal greeting + "Thank you for reaching out." + answer + "Feel free to ask anything else." + signature + ticket reference + footer

### WhatsApp
- **Format**: Friendly brief opening + direct answer (under 300 chars preferred) + offer to help more

### Web Form
- **Format**: Semi-formal greeting + answer in 2-3 paragraphs + call to action + signature

## 5. Escalation Rules (Finalized)

Escalate when:
- Keywords: lawyer, attorney, sue, legal, refund, billing, pricing, charge, dispute
- Sentiment < 0.3 (profanity, frustration, all caps > 50 chars)
- "human", "agent", "representative", "manager" mentioned
- After 2 failed KB searches (no relevant information)
- Message > 1000 words (too complex for automated handling)
- Feature request not in current roadmap
- Enterprise customer requiring dedicated support
- Any error in processing (automatic escalation)

## 6. Performance Baseline

From prototype testing:
- Knowledge search: <100ms (small dataset)
- Response generation (Claude API): ~2-3 seconds
- Channel formatting: <50ms
- Total processing time: ~3-4 seconds
- Expected delivery (async): <30 seconds
- Target accuracy: >85% on test set
- Target escalation rate: <20%

## 7. Migration Summary Table

| Incubation Component | Production Component | Status |
|---------------------|---------------------|--------|
| `prototype_agent.py` | `agent/customer_success_agent.py` | Migrated |
| `mcp_server.py` tools | `agent/tools.py` @function_tool | Migrated |
| In-memory conversation state | PostgreSQL messages table | Migrated |
| Print statements | Structured logging (stdlib) | Migrated |
| Manual testing | pytest test suite | Created |
| Local file storage | PostgreSQL + pgvector embeddings | Migrated |
| Single-threaded execution | Async Kafka consumer workers | Migrated |
| Hardcoded config | Environment variables + ConfigMaps | Migrated |
| Direct API calls | Channel handlers with retry/failover | Migrated |
| Basic search (string matching) | pgvector semantic search (1536-dim) | Migrated |

## 8. Production Readiness Checklist (Completed before this checklist)

- [x] Database schema designed and created
- [x] Kafka topics defined (8 topics)
- [x] Channel handlers implemented (Gmail, WhatsApp, Web Form)
- [x] Kubernetes resource requirements estimated
- [x] API endpoints listed and implemented
- [x] Prompts extracted to `production/agent/prompts.py`
- [x] MCP tools converted to @function_tool
- [x] Pydantic input validation added to all tools
- [x] Error handling added to all tools
- [x] Transition test suite created
- [x] Documentation written

---

**Transition Status**: COMPLETE
**Ready for Production Deployment**: YES
**Date**: 2025-04-08
