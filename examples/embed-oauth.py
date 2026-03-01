"""
Embed OAuth — connect end-users' own accounts inside your product.

Use this pattern when your users need to authorize access to their own
Gmail, Notion, Slack, or other accounts (vs using your account's credentials).

The OAuth flow has three steps:
1. start_connect()  — generate the redirect URL, store connection_id in session
2. User authorizes  — redirect them to the URL; they approve on the provider
3. complete_connect() — called from your OAuth callback route to finalize

Usage:
    export M8TES_API_KEY=m8_...
    python embed-oauth.py
"""

from m8tes import M8tes

client = M8tes()

# ── Account-level setup (run once at startup) ─────────────────────────────────
# The teammate is shared across all users. Configure it with your own tools
# (api_key integrations you control) here. End-user OAuth is added per-user below.

assistant = client.teammates.create(
    name="customer assistant",
    tools=["notion", "gmail"],  # users connect their own accounts
    instructions=(
        "You are a helpful assistant. Use the user's connected apps to "
        "complete tasks on their behalf. Always confirm before sending "
        "emails or making changes."
    ),
)

print(f"Teammate created: {assistant.id}")

# ── Simulate the web request context ─────────────────────────────────────────
# In a real app these would be your web framework request/response objects.
# We simulate them here so the example is self-contained.

SESSION: dict[str, str] = {}  # stand-in for your session store


# ── Step 1: Start the OAuth flow ──────────────────────────────────────────────
# Call this from your "Connect Gmail" button handler.
# Store connection_id in the session before redirecting — you'll need it in step 3.


def start_gmail_connect(user_id: str, callback_url: str) -> str:
    """Returns the URL to redirect the user to for Gmail authorization."""
    conn = client.apps.connect_oauth(
        "gmail",
        redirect_uri=callback_url,
        user_id=user_id,
    )
    # Must store connection_id before redirect — it's required to finalize OAuth
    SESSION["connection_id"] = conn.connection_id
    SESSION["user_id"] = user_id
    return conn.authorization_url  # redirect user here


# ── Step 2: (user goes to redirect_url and authorizes in browser) ─────────────


# ── Step 3: Finalize the connection ───────────────────────────────────────────
# Call this from your OAuth callback route (the redirect_uri you set above).


def oauth_callback(code: str, state: str) -> None:
    """Called when the user returns from the OAuth provider.

    code and state come from the redirect query params.
    The backend validates them internally — just pass connection_id to complete.
    """
    connection_id = SESSION.get("connection_id", "")
    user_id = SESSION.get("user_id", "")

    client.apps.connect_complete(
        "gmail",
        connection_id=connection_id,
        user_id=user_id,
    )
    print(f"Gmail connected for user {user_id}")


# ── Connect an API-key integration (no OAuth needed) ─────────────────────────
# Some integrations (OpenAI, Anthropic, custom APIs) use an API key instead of OAuth.


def connect_openai(user_id: str, api_key: str) -> None:
    """Store an API key integration for an end-user."""
    client.apps.connect_api_key("openai", api_key=api_key, user_id=user_id)
    print(f"OpenAI connected for user {user_id}")


# ── Check connection status before running ────────────────────────────────────
# Guard runs so you don't kick off an agent that can't do anything useful.


def run_for_user(user_id: str, message: str) -> str:
    if not client.apps.is_connected("gmail", user_id=user_id):
        raise ValueError(f"User {user_id!r} has not connected Gmail yet.")

    run = client.runs.create_and_wait(
        teammate_id=assistant.id,
        message=message,
        user_id=user_id,  # all memory and tool access scoped to this user
    )
    return run.output or ""


# ── Demo: onboard a user and run ──────────────────────────────────────────────

USER_ID = "user_alice"
CALLBACK_URL = "https://yourapp.com/oauth/callback"

# Onboard the user (sets up their isolated profile)
client.users.create(user_id=USER_ID, name="Alice", email="alice@acme.com")

# Start OAuth — in production you'd redirect the browser here
redirect_url = start_gmail_connect(USER_ID, CALLBACK_URL)
print(f"Redirect user to: {redirect_url}")

# In production, oauth_callback() is called by your web framework when the user
# returns after authorizing. Here we just show the function signature.
print("After user authorizes, call oauth_callback(code=..., state=...) from your callback route.")

# Check connection (will be False until real OAuth completes)
connected = client.apps.is_connected("gmail", user_id=USER_ID)
print(f"Gmail connected: {connected}")

# Once connected, run on their behalf
if connected:
    response = run_for_user(USER_ID, "Summarize my unread emails from today.")
    print(f"\nResponse: {response[:300]}...")
else:
    print("\nSkipping run — Gmail not connected yet.")

# ── List all connected apps for a user ────────────────────────────────────────

apps = client.apps.list(user_id=USER_ID)
for app in apps.data:
    status = "connected" if app.connected else "not connected"
    print(f"  {app.name}: {status}")
