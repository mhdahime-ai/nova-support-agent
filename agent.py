"""
Customer-facing support agent.

Uses Claude's tool-use to:
  - look up a customer's account in the (mock) CRM
  - search the FAQ knowledge base
  - escalate to a human when it can't resolve something

Swap `lookup_customer` for a real CRM API call (HubSpot, Salesforce, Zendesk, etc.)
when you're ready to go beyond the mock data.
"""

import json
import os
from pathlib import Path

import anthropic

DATA_DIR = Path(__file__).parent / "data"
MODEL = "claude-sonnet-4-5"

SYSTEM_PROMPT = """You are a customer support agent for a SaaS company called Nova.

Your job:
1. Answer customer questions using the FAQ knowledge base and, when relevant,
   their account details from the CRM.
2. Be warm, concise, and direct. Don't pad answers with filler.
3. If a customer gives their email, look them up so you can give specific,
   account-aware answers (e.g. plan details, billing status).
4. Escalate to a human when:
   - the customer explicitly asks for a human / manager
   - the issue involves a billing dispute, refund request, or account cancellation
     that you can't resolve with information alone
   - the customer is angry/frustrated and the FAQ isn't resolving it
   - you don't have enough information in the FAQ or CRM to answer confidently
   When you escalate, call the escalate tool with a clear reason and a short
   summary of the conversation so a human can pick it up with full context.
5. Never make up account details, refunds, or policies that aren't in the tools'
   results. If you don't know, say so and escalate.
"""

TOOLS = [
    {
        "name": "lookup_customer",
        "description": "Look up a customer's account details in the CRM by email address.",
        "input_schema": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "description": "The customer's email address"}
            },
            "required": ["email"],
        },
    },
    {
        "name": "search_faq",
        "description": "Search the FAQ knowledge base for relevant answers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "The customer's question or topic"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "escalate",
        "description": "Escalate this conversation to a human support agent.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {
                    "type": "string",
                    "description": "Short reason for escalation, e.g. 'refund dispute', 'angry customer', 'unresolvable technical issue'",
                },
                "summary": {
                    "type": "string",
                    "description": "A short summary of the conversation and what the customer needs, for the human agent to pick up with context",
                },
                "customer_email": {
                    "type": "string",
                    "description": "The customer's email if known, otherwise empty string",
                },
            },
            "required": ["reason", "summary", "customer_email"],
        },
    },
]


def _load_json(filename):
    with open(DATA_DIR / filename) as f:
        return json.load(f)


def lookup_customer(email: str) -> dict:
    customers = _load_json("customers.json")["customers"]
    for c in customers:
        if c["email"].lower() == email.lower().strip():
            return c
    return {"error": f"No customer found with email {email}"}


def search_faq(query: str) -> dict:
    faqs = _load_json("faqs.json")["faqs"]
    query_words = set(query.lower().split())
    scored = []
    for faq in faqs:
        faq_words = set((faq["question"] + " " + faq["answer"]).lower().split())
        overlap = len(query_words & faq_words)
        if overlap > 0:
            scored.append((overlap, faq))
    scored.sort(key=lambda x: -x[0])
    top = [f for _, f in scored[:3]]
    if not top:
        return {"results": [], "note": "No matching FAQ found."}
    return {"results": top}


def escalate(reason: str, summary: str, customer_email: str) -> dict:
    from escalations import log_escalation

    entry = log_escalation(reason=reason, summary=summary, customer_email=customer_email)
    return {"status": "escalated", "case_id": entry["id"]}


TOOL_FUNCTIONS = {
    "lookup_customer": lambda inp: lookup_customer(inp["email"]),
    "search_faq": lambda inp: search_faq(inp["query"]),
    "escalate": lambda inp: escalate(inp["reason"], inp["summary"], inp.get("customer_email", "")),
}


def get_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Add it to your .env locally or to your Render environment variables."
        )
    return anthropic.Anthropic(api_key=api_key)


def run_agent(conversation_history: list[dict]) -> dict:
    """
    conversation_history: list of {"role": "user"|"assistant", "content": str or list}
    Returns: {"reply": str, "escalated": bool, "case_id": str|None, "history": list}
    """
    client = get_client()
    messages = list(conversation_history)
    escalated = False
    case_id = None

    # Agentic loop: keep going while Claude wants to use tools
    for _ in range(6):  # safety cap on tool-call rounds
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            # Final text answer
            reply_text = "".join(
                block.text for block in response.content if block.type == "text"
            )
            messages.append({"role": "assistant", "content": response.content})
            return {
                "reply": reply_text,
                "escalated": escalated,
                "case_id": case_id,
                "history": messages,
            }

        # Handle tool use
        messages.append({"role": "assistant", "content": response.content})
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            func = TOOL_FUNCTIONS.get(block.name)
            result = func(block.input) if func else {"error": "unknown tool"}
            if block.name == "escalate":
                escalated = True
                case_id = result.get("case_id")
            tool_results.append(
                {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                }
            )
        messages.append({"role": "user", "content": tool_results})

    return {
        "reply": "I'm having trouble resolving this — let me get a human to help.",
        "escalated": escalated,
        "case_id": case_id,
        "history": messages,
    }
