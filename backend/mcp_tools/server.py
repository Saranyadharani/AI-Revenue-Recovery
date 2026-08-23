"""
server.py - wires our 3 recovery actions up as an actual MCP server.

using the official python mcp sdk (fastmcp). this is what lets the langchain
agent call these as real "tools" instead of just importing functions directly -
which was kind of the whole point of using mcp here, to have a proper bounded
tool layer with typed inputs instead of the agent freeform calling python.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mcp.server.fastmcp import FastMCP
from mcp_tools.actions import retry_payment, send_recovery_link, escalate_to_human

mcp = FastMCP("revenue-recovery-tools")


@mcp.tool()
def retry_payment_tool(txn_id: int) -> dict:
    """Retry a failed payment for the given transaction id. Only call this
    after checking the circuit breaker policy allows it."""
    return retry_payment(txn_id)


@mcp.tool()
def send_recovery_link_tool(txn_id: int) -> dict:
    """Send a payment recovery link (sms/email) to the customer for the
    given transaction id."""
    return send_recovery_link(txn_id)


@mcp.tool()
def escalate_to_human_tool(txn_id: int) -> dict:
    """Escalate this transaction to a human agent, stop automated attempts."""
    return escalate_to_human(txn_id)


if __name__ == "__main__":
    # run with: python server.py
    mcp.run()
