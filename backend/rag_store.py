"""
It is small curated "knowledge base" the agent pulls from before deciding what to do.docs are just python strings for now - kept it small on purpose (~15 docs)
instead of dumping in a huge scraped dataset, since quality > volume using a super basic keyword-overlap retriever instead of a vector db because
honestly for 15 docs a real embedding search is overkill. if this needed to scale to thousands of docs id switch to chroma/faiss.
"""

DOCS = [
    {
        "id": "fc_insufficient_funds",
        "text": "insufficient_funds means the customer's account did not have enough "
                "balance at the time of charge. best recovery action is to wait a short "
                "period and retry, or send a payment link so they can pay when funds are available. "
                "do not retry immediately back to back, banks often decline repeat attempts within minutes.",
    },
    {
        "id": "fc_card_declined",
        "text": "card_declined is a generic decline from the issuing bank. could be due to "
                "risk rules on the bank's side. recommended action is to send a recovery link "
                "so the customer can try a different payment method, rather than retrying the same card.",
    },
    {
        "id": "fc_bank_server_down",
        "text": "bank_server_down means the issuing bank's server timed out or was unreachable. "
                "this is usually a temporary infra issue, not the customer's fault. safe to auto-retry "
                "once after a short delay.",
    },
    {
        "id": "fc_expired_card",
        "text": "expired_card means the card used is no longer valid. retrying will never work here. "
                "correct action is to send a recovery link asking the customer to update their card, "
                "never auto-retry.",
    },
    {
        "id": "fc_otp_timeout",
        "text": "otp_timeout happens when customer didn't enter the otp in time. usually just a "
                "distraction, not a real failure. safe to retry once, and if it fails again send a "
                "recovery link instead of retrying further.",
    },
    {
        "id": "fc_issuer_unavailable",
        "text": "issuer_unavailable means the customer's bank systems are down. safe to auto retry "
                "after a delay, similar to bank_server_down.",
    },
    {
        "id": "fc_cart_left_at_payment",
        "text": "cart_left_at_payment means customer reached the payment step but didn't complete it. "
                "best recovery is a gentle reminder / recovery link, not a retry since no charge was "
                "even attempted.",
    },
    {
        "id": "fc_cart_left_at_otp",
        "text": "cart_left_at_otp - customer dropped off during otp verification. send a recovery link, "
                "there's nothing to retry since the transaction never completed.",
    },
    {
        "id": "fc_session_timeout",
        "text": "session_timeout means the checkout session expired before the customer finished. "
                "send a recovery link with a fresh checkout session.",
    },
    {
        "id": "fc_invoice_overdue_7d",
        "text": "invoice overdue by 7 days - early stage, still a soft nudge. send a friendly "
                "recovery link / reminder. do not escalate yet.",
    },
    {
        "id": "fc_invoice_overdue_15d",
        "text": "invoice overdue by 15 days - mid stage. send a firmer reminder, and if this is the "
                "customer's second overdue invoice, flag for escalation.",
    },
    {
        "id": "fc_invoice_overdue_30d",
        "text": "invoice overdue by 30+ days - this should be escalated to a human collections agent, "
                "automated nudges alone are not appropriate at this stage.",
    },
    {
        "id": "policy_retry_limits",
        "text": "policy: payment failures get a maximum of 3 automated retry/recovery attempts before "
                "mandatory escalation to a human. this is modeled loosely on RBI's guidelines around "
                "recurring payment (autopay/mandate) retries, which discourage excessive retry attempts "
                "on customers without consent.",
    },
    {
        "id": "policy_no_retry_on_hard_fail",
        "text": "policy: some failures should never be auto-retried because retrying cannot possibly "
                "fix them - expired_card is the main example. auto-retrying a hard failure wastes an "
                "attempt and annoys the customer.",
    },
    {
        "id": "policy_escalation",
        "text": "policy: once a transaction hits its max attempt limit, or is a 30+ day overdue invoice, "
                "stop automated action and escalate to a human agent with full context of what was tried.",
    },
]


def retrieve(query, top_k=3):
    query_words = set(query.lower().replace("_", " ").split())

    scored = []
    for doc in DOCS:
        doc_words = set(doc["text"].lower().replace("_", " ").split())
        overlap = len(query_words & doc_words)
        if overlap > 0:
            scored.append((overlap, doc))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:top_k]]


if __name__ == "__main__":
    # quick manual test
    results = retrieve("card_declined")
    for r in results:
        print(r["id"], "-", r["text"][:80])
