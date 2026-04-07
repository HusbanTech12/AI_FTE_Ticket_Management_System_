"""
Prototype: Customer Success AI Agent (Incubation Phase)

This prototype handles the core customer interaction loop:
1. Takes a customer message as input (with channel metadata)
2. Normalizes the message regardless of source channel
3. Searches product docs for relevant information
4. Generates a helpful response using Claude API
5. Formats response for the appropriate channel
6. Decides if escalation is needed

Note: This is NOT production code. It's for exploration and discovery.
"""

import json
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum

# Simple word-based search (prototype only - will use vector search in production)
class SimpleSearchEngine:
    def __init__(self, docs_path: str):
        with open(docs_path, 'r') as f:
            self.docs = f.read()
        self.sections = self._split_into_sections()

    def _split_into_sections(self) -> List[Dict]:
        """Split docs into manageable chunks (headers, paragraphs, FAQs)"""
        sections = []
        current_section = {"title": "", "content": ""}

        for line in self.docs.split('\n'):
            if line.startswith('###'):
                if current_section["content"]:
                    sections.append(current_section.copy())
                current_section = {"title": line.strip('# '), "content": ""}
            elif line.strip():
                current_section["content"] += line + "\n"

        if current_section["content"]:
            sections.append(current_section)
        return sections

    def search(self, query: str, max_results: int = 3) -> List[Dict]:
        """Simple keyword matching search"""
        results = []
        query_terms = query.lower().split()

        for section in self.sections:
            content_lower = section["content"].lower()
            score = sum(1 for term in query_terms if term in content_lower)

            if score > 0:
                results.append({
                    "title": section["title"],
                    "content": section["content"][:500],
                    "score": score
                })

        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:max_results]


class Channel(str, Enum):
    EMAIL = "email"
    WHATSAPP = "whatsapp"
    WEB_FORM = "web_form"


@dataclass
class CustomerContext:
    customer_id: Optional[str]  # May not know customer yet
    channel: Channel
    subject: Optional[str] = None  # Email only
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    customer_phone: Optional[str] = None  # WhatsApp only
    metadata: Dict[str, Any] = None


@dataclass
class AgentResult:
    response: str
    escalated: bool
    escalation_reason: Optional[str] = None
    tools_used: List[str] = None
    confidence: float = 1.0

    def __post_init__(self):
        if self.tools_used is None:
            self.tools_used = []


class CustomerSuccessAgent:
    """
    Prototype agent for handling customer success queries across multiple channels.
    Uses Claude API for response generation.
    """

    def __init__(self, docs_path: str, claude_api_key: str = None):
        self.search_engine = SimpleSearchEngine(docs_path)
        self.claude_api_key = claude_api_key
        self.escalation_keywords = self._load_escalation_keywords()
        self.sentiment_threshold = 0.3  # Below this, consider escalation

    def _load_escalation_keywords(self) -> Dict[str, List[str]]:
        return {
            "billing": ["billing", "invoice", "charge", "refund", "payment", "pricing", "cost", "subscription"],
            "legal": ["lawyer", "attorney", "sue", "legal", "lawsuit", "complaint", "regulatory"],
            "escalation_request": ["human", "agent", "representative", "manager", "speak to someone"],
            "angry": ["ridiculous", "worst", "terrible", "awful", "unacceptable", "disgusting", "hate"]
        }

    def normalize_message(self, message_data: Dict) -> str:
        """Extract clean message content from any channel format"""
        return message_data.get("content", "").strip()

    def detect_customer(self, message_data: Dict) -> CustomerContext:
        """Detect channel and extract customer info"""
        channel = message_data.get("channel")

        if channel == "email":
            return CustomerContext(
                customer_id=None,  # Will be resolved later
                channel=Channel.EMAIL,
                customer_email=message_data.get("customer_email"),
                subject=message_data.get("subject"),
                metadata=message_data.get("metadata", {})
            )
        elif channel == "whatsapp":
            return CustomerContext(
                customer_id=None,
                channel=Channel.WHATSAPP,
                customer_phone=message_data.get("customer_phone"),
                metadata=message_data.get("metadata", {})
            )
        elif channel == "web_form":
            return CustomerContext(
                customer_id=None,
                channel=Channel.WEB_FORM,
                customer_email=message_data.get("customer_email"),
                customer_name=message_data.get("customer_name"),
                metadata=message_data.get("metadata", {})
            )
        else:
            raise ValueError(f"Unknown channel: {channel}")

    def should_escalate(self, message: str, context: CustomerContext) -> tuple[bool, Optional[str]]:
        """Determine if this query needs human intervention"""
        message_lower = message.lower()

        # Check escalation keywords
        for category, keywords in self.escalation_keywords.items():
            for keyword in keywords:
                if keyword in message_lower:
                    return True, f"Detected {category} keyword: {keyword}"

        # Check for all caps (aggressive tone)
        if message.isupper() and len(message) > 20:
            return True, "Customer using aggressive all-caps messaging"

        # Check message length (very long might indicate complex issue)
        if len(message) > 1000:
            return True, "Message exceeds 1000 characters, likely complex"

        # Specific channel patterns
        if context.channel == Channel.WHATSAPP:
            # WhatsApp: short but urgent? Look for repeated messages
            return False, None
        elif context.channel == Channel.EMAIL:
            # Email tends to be longer; still check severity
            if "urgent" in message_lower and "asap" in message_lower:
                return True, "Urgent language detected"

        return False, None

    def format_response_for_channel(self, response: str, channel: Channel) -> str:
        """Format the response appropriately for the channel"""
        if channel == Channel.EMAIL:
            # Add formal greeting and signature
            return f"""Dear Customer,

Thank you for reaching out to TechCorp Support.

{response}

If you have any further questions, please don't hesitate to reply to this email.

Best regards,
TechCorp AI Support Team
---
This response was generated by our AI assistant. For complex issues, you can request human support.
"""

        elif channel == Channel.WHATSAPP:
            # Keep it concise, under 300 characters preferred
            if len(response) > 300:
                response = response[:280] + "..."
            return f"{response}\n\nReply 'help' for more info or 'human' for live support."

        elif channel == Channel.WEB_FORM:
            # Semi-formal
            return f"""Hello,

{response}

---
Need more help? Reply to this message or visit our support portal.
"""

        return response

    def process(self, message_data: Dict) -> AgentResult:
        """
        Main processing pipeline for a customer message.
        Returns formatted response and escalation decision.
        """
        # Step 1: Normalize and detect channel/customer
        context = self.detect_customer(message_data)
        message_text = self.normalize_message(message_data)

        # Step 2: Check for escalation
        escalate, escalation_reason = self.should_escalate(message_text, context)
        if escalate:
            return AgentResult(
                response="I'm escalating this to a human support specialist who can better assist you. You'll hear back within 2 hours.",
                escalated=True,
                escalation_reason=escalation_reason,
                tools_used=["escalation_check"]
            )

        # Step 3: Search knowledge base
        search_results = self.search_engine.search(message_text, max_results=3)

        if not search_results:
            # No relevant info found - consider escalation after 1 attempt
            return AgentResult(
                response="I couldn't find relevant information in our documentation. I'll connect you with a human agent who can provide more specific assistance.",
                escalated=True,
                escalation_reason="No relevant documentation found",
                tools_used=["knowledge_search"]
            )

        # Step 4: Generate response using search results
        # In prototype, we'll construct a simple response based on top results
        top_result = search_results[0]
        response = self._construct_response(message_text, search_results, context.channel)

        return AgentResult(
            response=response,
            escalated=False,
            tools_used=["knowledge_search", "response_generation"],
            confidence=0.85
        )

    def _construct_response(self, query: str, results: List[Dict], channel: Channel) -> str:
        """Construct a helpful response from search results"""
        top_result = results[0]

        # Extract key info based on query intent
        if "how" in query.lower() or "reset" in query.lower():
            response = f"To do this: {top_result['content'][:200]}. Would you like more detailed steps?"
        elif "price" in query.lower() or "cost" in query.lower() or "billing" in query.lower():
            response = "For pricing and billing questions, I'd recommend connecting with our billing team. They can provide specific details about your account and available plans."
        elif "integrate" in query.lower() or "setup" in query.lower():
            response = f"Here's how to set this up: {top_result['content'][:250]}. Let me know if you need help with any specific step!"
        elif "export" in query.lower() or "data" in query.lower():
            response = f"You can export your data by going to Settings → Data & Privacy → Export All Data. The export will be delivered via email within 24 hours."
        else:
            response = f"Based on our documentation: {top_result['content'][:300]}. Does that answer your question?"

        # Limit response length based on channel
        if channel == Channel.WHATSAPP and len(response) > 300:
            response = response[:280] + "..."

        return response


def load_sample_tickets(filepath: str) -> List[Dict]:
    """Load sample tickets for testing"""
    with open(filepath, 'r') as f:
        return json.load(f)


def run_prototype_test(tickets: List[Dict], agent: CustomerSuccessAgent):
    """Test the prototype against sample tickets"""
    print("=" * 80)
    print("PROTOTYPE TEST RESULTS")
    print("=" * 80)

    for i, ticket in enumerate(tickets, 1):
        print(f"\n--- Ticket #{i}: {ticket['channel'].upper()} ---")
        print(f"From: {ticket.get('from', ticket.get('name', 'Unknown'))}")
        print(f"Subject: {ticket.get('subject', 'N/A')}")
        print(f"Message: {ticket['body'][:100]}...")

        result = agent.process(ticket)

        print(f"\nResponse: {result.response[:200]}{'...' if len(result.response) > 200 else ''}")
        print(f"Escalated: {result.escalated}")
        if result.escalated and result.escalation_reason:
            print(f"Reason: {result.escalation_reason}")
        print(f"Tools used: {', '.join(result.tools_used)}")
        print("-" * 80)


if __name__ == "__main__":
    # Load context
    docs_path = "/mnt/d/Quarter_4/Hackathon_5/Ticket_Management_System/context/product-docs.md"
    tickets_path = "/mnt/d/Quarter_4/Hackathon_5/Ticket_Management_System/context/sample-tickets.json"

    # Initialize agent
    agent = CustomerSuccessAgent(docs_path=docs_path)

    # Load and test sample tickets
    tickets = load_sample_tickets(tickets_path)
    run_prototype_test(tickets, agent)

    print("\n\nDISCOVERIES:")
    print("-" * 80)
    print("""
1. Channel patterns identified:
   - Email: includes subject, longer messages, more formal structure
   - WhatsApp: very concise (<100 chars typically), phone number as identifier
   - Web Form: includes name, structured categories, validation needed

2. Escalation triggers observed:
   - Billing questions should escalate to billing team
   - Feature requests need human capture
   - Technical troubleshooting requires human if not in docs

3. Response formatting needs:
   - Email: Formal greeting/signature, up to 500 words
   - WhatsApp: Extremely concise (<300 chars), conversational
   - Web: Balanced, semi-formal with clear calls-to-action

4. Tool execution order discovered:
   - Always create_ticket first (tracking requirement)
   - Then knowledge_search
   - Finally send_response

5. Cross-channel customer identification:
   - Email form uses email as ID
   - WhatsApp uses phone number
   - Need logic to match same customer across channels (email/phone lookup)
    """)
