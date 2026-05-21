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
from .tools.financial_metrics import calculate_financial_metrics
from .tools.operational_metrics import calculate_operational_metrics
from .tools.entity_details import get_entity_details
from .tools.explain_flags import explain_flagged_item

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6-20250514"
MAX_TOKENS = 4096
MAX_TOOL_ROUNDS = 5  # prevent infinite loops

_PROACTIVE_TRIGGERS = frozenset({
    "start", "begin", "analyze", "review", "hello", "hi",
    "go", "analyse", "open", "show",
})

PARITY_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "calculate_financial_metrics",
        "description": (
            "Calculate critical financial metrics: DSCR (Debt Service Coverage Ratio), "
            "revenue growth, cash flow volatility, burn rate, and loan repayment burden. "
            "Use when asked about financial health, debt capacity, or profitability."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "calculate_operational_metrics",
        "description": (
            "Calculate operational health metrics: supplier concentration, customer concentration, "
            "working capital trend, and payroll stability. Use when asked about operational risks, "
            "concentration risk, or business stability."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_entity_details",
        "description": (
            "Get full transaction history and risk profile for a specific entity "
            "(supplier, customer, or counterparty). Use when asked about a specific "
            "company, person, or RTGS reference."
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
            "Explain why a specific entity or transaction is flagged for review. "
            "Returns anomaly details, severity breakdown, and recommended analyst action. "
            "Use when asked why something is flagged or needs review."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "entity_name": {
                    "type": "string",
                    "description": "The name of the flagged entity to explain.",
                }
            },
            "required": ["entity_name"],
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
    if name == "calculate_financial_metrics":
        return calculate_financial_metrics(deal_data)
    if name == "calculate_operational_metrics":
        return calculate_operational_metrics(deal_data)
    if name == "get_entity_details":
        return get_entity_details(tool_input["entity_name"], deal_data)
    if name == "explain_flagged_item":
        return explain_flagged_item(tool_input["entity_name"], deal_data)
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
