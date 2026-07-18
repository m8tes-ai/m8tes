"""
Configure a agent to receive Apple Messages through a BlueBubbles bridge.

Usage:
    export M8TES_API_KEY=m8_...
    python examples/imessage-bluebubbles.py

iMessage is per-customer: you run your own BlueBubbles server (on your own Mac,
under your own Apple ID). Register it once as a bridge, point the BlueBubbles
webhook at m8tes using the returned secret, then bind a agent to a chat on
that bridge with an explicit sender allowlist (routing is fail-closed).
"""

from m8tes import M8tes

client = M8tes()

# 1. Register your BlueBubbles server as a bridge. The webhook secret is shown
#    ONCE — configure it as the BlueBubbles webhook secret right now.
bridge = client.bridges.create(
    name="my mac",
    server_url="https://bluebubbles.example.com",
    password="your-bluebubbles-api-password",
)
print(f"bridge:        {bridge.id}")
print(f"webhook secret (save now, shown once): {bridge.webhook_secret}")
print("point your BlueBubbles webhook at POST /api/v1/webhooks/inbound/imessage")
print("with header  X-Webhook-Secret: <the secret above>")

# 2. Bind a agent to a chat on that bridge. allowed_imessage_senders is
#    required — only listed handles can trigger the agent (fail-closed).
agent = client.agents.create(
    name="messages concierge",
    instructions=(
        "reply with short, direct answers, ask clarifying questions when needed, "
        "and confirm any sensitive action before you take it"
    ),
    inbound_imessage_enabled=True,
    bridge_id=bridge.id,
    imessage_chat_guid="iMessage;-;+15551231234",
    allowed_imessage_senders=["+15551231234"],
)

print(f"agent:  {agent.id}")
print(f"chat guid: {agent.imessage_chat_guid}")
print("BlueBubbles will now route that chat to this agent.")
