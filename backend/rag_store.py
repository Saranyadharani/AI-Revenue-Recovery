"""
rag_store.py - simple keyword-based retrieval for failure docs + policy docs.
in production this would be a vector store (chroma/weaviate/pinecone), but
for the demo we keep it simple and deterministic.
"""

import os
import json

# hardcoded failure + policy docs for the demo.
# in production these would be loaded from a database or vector store.

FAILURE_DOCS = {
    "insufficient_funds": {
        "id": "fc_insufficient_funds",
        "text": """Failure Code: insufficient_funds
The customer's account does not have enough available balance to complete the transaction.
Recommended action: send_recovery_link
Why: The customer needs to add funds or use a different payment method. A retry will fail again unless the balance changes."""
    },
    "card_declined": {
        "id": "fc_card_declined",
        "text": """Failure Code: card_declined
The card issuer declined the transaction. This could be due to fraud prevention, card restrictions, or the card being blocked.
Recommended action: send_recovery_link
Why: The customer needs to contact their bank or use a different card. A retry without customer action is unlikely to succeed."""
    },
    "bank_server_down": {
        "id": "fc_bank_server_down",
        "text": """Failure Code: bank_server_down
The bank's payment processing system is temporarily unavailable.
Recommended action: retry_payment
Why: This is a transient technical issue. A retry after a short delay will likely succeed."""
    },
    "expired_card": {
        "id": "fc_expired_card",
        "text": """Failure Code: expired_card
The card used for the transaction has expired.
Recommended action: send_recovery_link
Why: The customer needs to update their card details. A retry will fail with the same card."""
    },
    "otp_timeout": {
        "id": "fc_otp_timeout",
        "text": """Failure Code: otp_timeout
The customer did not complete the OTP verification within the allowed time.
Recommended action: send_recovery_link
Why: The customer needs to try again with a fresh OTP session. A retry without a new OTP will fail."""
    },
    "issuer_unavailable": {
        "id": "fc_issuer_unavailable",
        "text": """Failure Code: issuer_unavailable
The card issuer is not responding to the authorization request.
Recommended action: retry_payment
Why: This is a temporary connectivity issue. A retry after a short delay will likely succeed."""
    },
    "cart_left_at_payment": {
        "id": "fc_cart_left_at_payment",
        "text": """Failure Code: cart_left_at_payment
The customer reached the payment page but abandoned the checkout before completing the transaction.
Recommended action: send_recovery_link
Why: The customer showed intent but didn't complete. A reminder with a recovery link can bring them back."""
    },
    "cart_left_at_otp": {
        "id": "fc_cart_left_at_otp",
        "text": """Failure Code: cart_left_at_otp
The customer started the OTP verification but abandoned the checkout.
Recommended action: send_recovery_link
Why: The customer was close to completing. A recovery link with a fresh OTP session can help."""
    },
    "session_timeout": {
        "id": "fc_session_timeout",
        "text": """Failure Code: session_timeout
The customer's session expired before they completed the checkout.
Recommended action: send_recovery_link
Why: The customer needs to start a fresh session. A recovery link can take them directly back to checkout."""
    },
    "invoice_overdue_7d": {
        "id": "fc_invoice_overdue_7d",
        "text": """Failure Code: invoice_overdue_7d
The invoice is 7 days overdue.
Recommended action: send_recovery_link
Why: Early-stage overdue. A gentle reminder with a payment link is appropriate."""
    },
    "invoice_overdue_15d": {
        "id": "fc_invoice_overdue_15d",
        "text": """Failure Code: invoice_overdue_15d
The invoice is 15 days overdue.
Recommended action: send_recovery_link
Why: Mid-stage overdue. A stronger reminder with a payment link is appropriate."""
    },
    "invoice_overdue_30d": {
        "id": "fc_invoice_overdue_30d",
        "text": """Failure Code: invoice_overdue_30d
The invoice is 30+ days overdue.
Recommended action: escalate_to_human
Why: Long-term overdue. This requires human intervention as automated attempts are unlikely to succeed."""
    },
}

POLICY_DOCS = [
    {
        "id": "policy_consent_and_contact_limits",
        "text": """Policy: Consent and Contact Limits
1. Customers must have explicitly opted in to receive recovery communications.
2. Recovery contacts are limited to: 1 SMS, 1 email, 1 push notification per 24-hour period.
3. If a customer has not responded after 3 contact attempts, the case must be escalated to human review.
4. Customers can opt out of recovery communications at any time by replying STOP or clicking the unsubscribe link."""
    },
    {
        "id": "policy_retry_limits",
        "text": """Policy: Retry Limits
1. Payment retries are allowed only for transient/technical failures (e.g., bank_server_down, issuer_unavailable).
2. A maximum of 3 retry attempts is allowed per transaction.
3. After 3 failed retries, the transaction must be escalated to human review."""
    },
    {
        "id": "policy_escalation",
        "text": """Policy: Escalation Rules
1. Escalation is required for:
   - invoice_overdue_30d or older
   - transactions with expired cards that the customer has not updated after 7 days
   - any transaction where the customer has explicitly requested human assistance
2. Escalated transactions are sent to the human collections team for review."""
    },
]


def retrieve(query, top_k=3):
    """
    Simple keyword-based retrieval.
    Always includes all policy docs plus the most relevant failure docs.
    """
    results = []
    
    # Add ALL policy docs first (universal application)
    results.extend(POLICY_DOCS)
    
    # Find matching failure docs based on keywords in the query
    query_lower = query.lower()
    matched_failure_docs = []
    
    for failure_code, doc in FAILURE_DOCS.items():
        # Check if the failure_code or its text matches the query
        if (failure_code.lower() in query_lower or 
            any(word in doc["text"].lower() for word in query_lower.split())):
            matched_failure_docs.append(doc)
    
    # Add the top_k most relevant failure docs (limit to top_k)
    # In a real system, you'd use a more sophisticated ranking
    results.extend(matched_failure_docs[:top_k])
    
    # Ensure we don't return duplicates
    seen_ids = set()
    unique_results = []
    for doc in results:
        if doc["id"] not in seen_ids:
            seen_ids.add(doc["id"])
            unique_results.append(doc)
    
    return unique_results


# Combined DOCS for agent.py to import
DOCS = list(FAILURE_DOCS.values()) + POLICY_DOCS