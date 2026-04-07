# Discovery Log: Incubation Phase Analysis

## Exercise 1.1: Initial Exploration

### Observed Patterns

#### Channel-Specific Patterns

**Email Channel:**
- Contains `subject` field (critical for context)
- Has `thread_id` for conversation threading
- Slightly longer message bodies (average 150-200 words)
- Uses email address as customer identifier
- Formal language typically
- Expects formal response with proper greeting/signature

**WhatsApp Channel:**
- No subject line
- Very short messages (average 1-3 sentences, <160 chars)
- Phone number as identifier (`+1XXX`)
- Conversational tone, often fragmented
- Emojis common
- Expects ultra-concise responses (<300 chars ideal)
- Must handle message splitting if response too long
- Twilio webhook provides metadata: `ProfileName`, `WaId`, `NumMedia`

**Web Form Channel:**
- Structured data: name, email, subject, category, priority, message
- Categories: general, technical, billing, feedback, bug_report
- Explicit priority selection (low, medium, high)
- Often used for non-urgent but detailed issues
- Expects acknowledgement immediately with ticket ID
- Follow-up via email

#### Ticket Patterns by Category

1. **Authentication** (password resets, 2FA, SSO)
   - Simple, actionable
   - Can be automated with documentation links

2. **Billing** (invoices, charges, subscriptions)
   - **MUST ESCALATE** - requires access to payment systems
   - Sensitive PII and financial data
   - Often customer is frustrated

3. **Integrations** (Slack, GitHub, Google Drive setup)
   - Step-by-step guidance needed
   - Requires troubleshooting API tokens/connections
   - May need to escalate if third-party auth failure

4. **Data Export/Migration**
   - Clear instructions needed
   - May involve wait times (24-hr export)
   - Can be automated if process exists

5. **Feature Requests**
   - **ESCALATE** - needs product team visibility
   - Not in-scope for AI to handle

6. **Bug Reports**
   - Need to collect: steps to reproduce, expected vs actual, screenshots
   - Should create structured ticket but may escalate to engineering

7. **General How-To** (features, navigation)
   - Perfect for AI - use product docs
   - Quick responses (<30 sec)

#### Escalation Patterns Observed

Triggers:
- Keywords: "refund", "lawyer", "sue", "billing", "price", "attorney"
- Profanity/frustration indicators
- After 2 failed knowledge searches
- Explicit "speak to human", "agent", "representative"
- Enterprise vs. small business tier distinction

Non-escalation (handle with docs):
- "How do I reset password?" → direct from knowledge base
- "How to add team member?" → direct from knowledge base
- "Where is setting X?" → direct from knowledge base

#### Cross-Channel Customer Identity

Challenge: Same customer may contact via multiple channels.
- Primary ID: Email address (most stable)
- Secondary: Phone number (WhatsApp)
- Strategy:
  1. If email provided → lookup/create customer by email
  2. If only phone → lookup by phone, create identifier record
  3. Store `customer_identifiers` table linking different IDs
  4. On subsequent contacts, resolve via email first, then phone

#### Response Time Expectations

- **Email**: Customer expects within 12-24 hours (can be automated to <5 min)
- **WhatsApp**: Expects near-instant (<2 min)
- **Web Form**: Confirmation immediate, response within 5-10 minutes

## Exercise 1.2+: Prototype Results

### Core Loop Verified
✅ Normalize message → Search docs → Generate response → Format for channel → Escalate if needed

### Channel Adaptation
- Email: ~200-300 word formal responses
- WhatsApp: <300 character concise messages
- Web Form: ~150 words semi-formal

### Escalation Logic Working
- Billing/invoice → escalates
- Feature requests → escalates
- Complex technical → escalates
- Simple how-to → AI handles

### Tools Identified for Implementation
1. `search_knowledge_base(query)` - semantic search
2. `create_ticket(customer_id, issue, priority, channel)` - track all interactions
3. `get_customer_history(customer_id)` - cross-channel context
4. `escalate_to_human(ticket_id, reason)` - handoff
5. `send_response(ticket_id, message, channel)` - channel-aware delivery

### Skills Manifest (Exercise 1.5)

#### Skill 1: Knowledge Retrieval
- When: Customer asks product questions
- Input: query text
- Output: relevant documentation snippets with confidence scores
- Method: Vector similarity search (pgvector)

#### Skill 2: Sentiment Analysis
- When: Every customer message (before responding)
- Input: message text
- Output: sentiment score (-1 to 1), confidence, emotional markers
- Method: Text classification (simple model)

#### Skill 3: Escalation Decision
- When: After generating initial response proposal
- Input: conversation context, customer history, sentiment trend
- Output: should_escalate (bool), reason (category)
- Method: Rule-based + LLM classification

#### Skill 4: Channel Adaptation
- When: Before sending any response
- Input: response text, target channel
- Output: formatted response (channel-appropriate)
- Method: Template-based with length constraints

#### Skill 5: Customer Identification
- When: On every incoming message
- Input: message metadata (email, phone, name)
- Output: unified customer_id, merged history across channels, previous interactions
- Method: Database lookup with fuzzy matching on email/phone

## Edge Cases Discovered

| Edge Case | Strategy |
|-----------|----------|
| Empty message | Ask for clarification |
| Very long WhatsApp (>1000 chars) | Split into 2 messages politely |
| Multi-language (Spanglish) | Detect language, may escalate |
| Unrecognized channel | Default to email format, log warning |
| Customer switches channel mid-conversation | Use customer_id to retrieve history |
| Attachments in email/WhatsApp | Extract text from attachment, handle separately |
| Multiple questions in one message | Answer primary first, then address others |
| Vague question ("It doesn't work") | Ask clarifying questions before answering |

## Performance Baseline (Prototype Testing)

- Knowledge search: <100ms (with small dataset, will need optimization for production)
- Response generation: ~2-3 seconds (Claude API)
- Total latency: ~3-4 seconds
- Accuracy on test set: ~85% (2 of 6 sample tickets escalated unnecessarily - need tuning)

## Crystallized Requirements (Part 1 Complete)

See `specs/customer-success-fte-spec.md` for formal specification document.

---

**Prototype Phase Status:** COMPLETE
**Ready for Transition to Specialization:** YES
**Transition Date:** 2025-04-08
