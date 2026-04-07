# Escalation Rules

## When to Escalate to Human Support

The AI agent **MUST escalate** when ANY of the following conditions are met:

### 1. Billing and Refunds
- Any mention of "refund", "chargeback", "dispute"
- Double billing or payment issues
- Subscription cancellation requests
- Pricing negotiation questions
- Refund requests (even if within 30 days)
- Payment failure beyond automated retries

### 2. Legal and Compliance
- Customer mentions "lawyer", "attorney", "sue", "legal action"
- Questions about GDPR, CCPA, or data privacy laws
- Requests for signed contracts or legal documentation
- Subpoenas or government requests
- Questions about data sovereignty

### 3. Angry or Frustrated Customers
- Customer uses profanity or aggressive language
- Sentiment score below 0.3 (on scale where negative is <0.5)
- ALL CAPS messages
- Repeated complaints about same issue
- Threats to leave or cancel immediately
- Expressions of extreme frustration: "This is RIDICULOUS", "WORST SERVICE EVER"

### 4. Feature Requests
- Requests for features not in current documentation
- Requests to modify existing core functionality
- Custom development requests
- Integration requests that require partner APIs not currently supported
- Questions about future roadmap or release dates

### 5. Technical Complexity
- Errors requiring database-level debugging
- Issues spanning multiple systems
- API errors that can't be resolved with standard troubleshooting
- Performance issues affecting entire projects
- Data corruption or loss reports
- Questions about internal architecture or processes

### 6. Security and Access
- Account compromise reports
- Unauthorized access concerns
- SSO setup failures
- Two-factor authentication issues requiring manual reset
- Requests to delete account/data under GDPR/CCPA

### 7. Explicit Human Request
- Customer says: "speak to a human", "agent", "representative", "manager"
- Customer says: "I want to talk to someone"
- Repeated requests for human despite AI responses
- Message contains "?"

### 8. Knowledge Gaps
- After 2 knowledge base searches with no relevant results
- When the product documentation doesn't cover the question
- Ambiguous questions that need clarification from subject matter expert
- Technical questions about architecture not in user-facing docs

### 9. Enterprise Customers
- Any contact from Enterprise plan customers (priority flag)
- Questions about custom contracts or SLAs
- SSO configuration requests
- Audit log requests
- Custom invoicing requirements

## Escalation Process

When escalating:
1. Call `escalate_to_human()` tool with clear reason
2. Include full conversation context
3. Publish to Kafka `fte.escalations` topic
4. Send immediate acknowledgment to customer: "I'm escalating this to our human support team. They will contact you within 2 hours."
5. Mark ticket status as "escalated" in database

## Resolution Without Escalation

The agent SHOULD NOT escalate for:
- Password resets (use automated reset flow)
- General "how-to" questions (documented in knowledge base)
- Simple bug reports (create ticket, acknowledge)
- Feature requests (log as feedback, provide roadmap link)
- Billing FAQs (use billing knowledge base)
- Configuration questions (provide step-by-step instructions)
- Integration setup issues (provide standard troubleshooting steps)
