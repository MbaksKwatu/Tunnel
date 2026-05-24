"""
Parity Review AI — chat handler using Claude Sonnet 4.6 with tool use.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

import anthropic

from .personalities import SME_DEBT_FUND_PERSONALITY
from .context import build_snapshot_context
from .proactive_analysis import generate_proactive_analysis
from . import formatters
from .tools.deal_summary import get_deal_summary
from .tools.financial_metrics import calculate_financial_metrics
from .tools.operational_metrics import calculate_operational_metrics
from .tools.entity_details import get_entity_details
from .tools.explain_flags import explain_flagged_item
from .tools.query_transactions import query_transactions

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096
MAX_TOOL_ROUNDS = 5  # prevent infinite loops

_PROACTIVE_TRIGGERS = frozenset({
    "start", "begin", "analyze", "review", "hello", "hi",
    "go", "analyse", "open", "show",
})

PARITY_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "get_deal_summary",
        "description": (
            "Return deal-level transaction counts and totals: credits vs debits (count and amount), "
            "breakdown by transaction role (revenue, supplier, payroll, tax, loan, needs_review), "
            "monthly inflow/outflow/net table, and distinct entity count."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "calculate_financial_metrics",
        "description": (
            "Compute financial metrics from transaction data: DSCR (Debt Service Coverage Ratio), "
            "revenue growth percentage, cash flow coefficient of variation, burn rate, "
            "and loan repayment as percentage of outflow."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "calculate_operational_metrics",
        "description": (
            "Compute operational metrics from transaction data: supplier concentration percentages, "
            "customer concentration percentages, working capital trend, and payroll frequency."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_entity_details",
        "description": (
            "Look up the full transaction history for a specific entity "
            "(supplier, customer, or counterparty). Returns transaction dates, amounts, "
            "reference codes, and totals."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "The entity name or partial name to look up.",
                }
            },
            "required": ["entity_name"],
        },
    },
    {
        "name": "explain_flagged_item",
        "description": (
            "Return data on why a specific entity or transaction is flagged. "
            "Returns the anomaly types, severity counts, and transaction details "
            "for the flagged items."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "The name of the flagged entity to look up.",
                }
            },
            "required": ["entity_name"],
        },
    },
    {
        "name": "query_transactions",
        "description": (
            "Search and filter individual transactions. Supports filtering by: "
            "role (needs_review, revenue_operational, supplier_payment, payroll, loan_repayment, tax_payment), "
            "minimum/maximum amount in cents, entity name substring, date range (YYYY-MM-DD), "
            "and anomaly presence. Returns matching transactions with txn_id, date, amount, "
            "description, entity name, and anomaly details. Sorted by amount descending."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "role": {
                    "type": "string",
                    "description": "Filter by transaction role (exact match).",
                },
                "min_amount_cents": {
                    "type": "integer",
                    "description": "Minimum absolute amount in cents (e.g. 500000 = 5,000 KES).",
                },
                "max_amount_cents": {
                    "type": "integer",
                    "description": "Maximum absolute amount in cents.",
                },
                "entity_name": {
                    "type": "string",
                    "description": "Entity name or description substring (case-insensitive).",
                },
                "date_from": {
                    "type": "string",
                    "description": "Start date inclusive (YYYY-MM-DD).",
                },
                "date_to": {
                    "type": "string",
                    "description": "End date inclusive (YYYY-MM-DD).",
                },
                "has_anomalies": {
                    "type": "boolean",
                    "description": "If true, only transactions with anomalies. If false, only clean.",
                },
            },
            "required": [],
        },
    },
]


def run_chat(
    message: str,
    deal_data: Dict[str, Any],
    conversation_history: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Send a message and return the AI response plus updated conversation history.

    On the first turn, if the message is a simple greeting/trigger word,
    returns a deterministic proactive analysis (no API call needed).
    Subsequent turns use Claude with prompt caching for faster responses.
    """
    is_first_message = not conversation_history
    msg_lower = message.strip().lower()

    if is_first_message and msg_lower in _PROACTIVE_TRIGGERS:
        proactive_response = generate_proactive_analysis(deal_data)
        return {
            "response": proactive_response,
            "conversation_history": [
                {"role": "user", "content": message},
                {"role": "assistant", "content": proactive_response},
            ],
            "tools_called": ["proactive_analysis"],
            "is_proactive": True,
            "usage": {
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_creation_input_tokens": 0,
                "cache_read_input_tokens": 0,
            },
        }

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)

    system_prompt = SME_DEBT_FUND_PERSONALITY + "\n\n" + build_snapshot_context(deal_data)

    messages: List[Dict[str, Any]] = list(conversation_history or [])
    messages.append({"role": "user", "content": message})

    tools_called: List[str] = []
    total_input_tokens  = 0
    total_output_tokens = 0
    cache_creation_tokens = 0
    cache_read_tokens = 0

    for _round in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=messages,
            tools=PARITY_TOOLS,
        )
        total_input_tokens  += response.usage.input_tokens
        total_output_tokens += response.usage.output_tokens
        cache_creation_tokens += getattr(response.usage, "cache_creation_input_tokens", 0)
        cache_read_tokens += getattr(response.usage, "cache_read_input_tokens", 0)

        if response.stop_reason != "tool_use":
            break

        # Execute all tool calls in this round
        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            tool_name  = block.name
            tool_input = block.input
            tools_called.append(tool_name)
            logger.info("[parity_review] tool_use name=%s input=%s", tool_name, tool_input)

            try:
                result = _dispatch_tool(tool_name, tool_input, deal_data)
                result = _enrich_with_formatting(tool_name, result)
            except Exception as exc:
                logger.exception("[parity_review] tool error name=%s", tool_name)
                result = {"error": str(exc)}

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result),
            })

        messages.append({"role": "assistant", "content": response.content})
        messages.append({"role": "user", "content": tool_results})

    # Extract final text
    text_response = "".join(
        block.text for block in response.content if hasattr(block, "text")
    )

    # Update history with final assistant turn (excluding raw tool_result entries)
    messages.append({"role": "assistant", "content": text_response})

    return {
        "response": text_response,
        "conversation_history": messages,
        "tools_called": tools_called,
        "usage": {
            "input_tokens": total_input_tokens,
            "output_tokens": total_output_tokens,
            "cache_creation_input_tokens": cache_creation_tokens,
            "cache_read_input_tokens": cache_read_tokens,
        },
    }


def _dispatch_tool(
    name: str,
    tool_input: Dict[str, Any],
    deal_data: Dict[str, Any],
) -> Dict[str, Any]:
    if name == "get_deal_summary":
        return get_deal_summary(deal_data)
    if name == "calculate_financial_metrics":
        return calculate_financial_metrics(deal_data)
    if name == "calculate_operational_metrics":
        return calculate_operational_metrics(deal_data)
    if name == "get_entity_details":
        return get_entity_details(tool_input["entity_name"], deal_data)
    if name == "explain_flagged_item":
        return explain_flagged_item(tool_input["entity_name"], deal_data)
    if name == "query_transactions":
        return query_transactions(tool_input, deal_data)
    return {"error": f"Unknown tool: {name}"}


def _enrich_with_formatting(
    tool_name: str,
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """Attach a pre-formatted markdown representation so the LLM can echo it."""
    if tool_name == "get_entity_details":
        result["formatted_response"] = formatters.format_entity_profile(result)
    elif tool_name == "explain_flagged_item":
        result["formatted_response"] = formatters.format_flag_explanation(result)
    return result
