"""Interactive CLI utilities for Meta Ads integration."""

from __future__ import annotations

from typing import TYPE_CHECKING
import webbrowser

from ..auth.url_helper import parse_callback_url
from ..exceptions import AuthenticationError, NetworkError, OAuthError, ValidationError

if TYPE_CHECKING:
    from ..client import M8tes


class MetaIntegrationCLI:
    """Interactive helper for managing Meta Ads integration."""

    def __init__(self, client: M8tes) -> None:
        self.client = client

    def connect_interactive(
        self,
        *,
        redirect_uri: str = "https://localhost:8080/callback",
        auto_browser: bool = True,
    ) -> None:
        """Guide user through Meta OAuth connection flow."""
        print("🚀 Setting up Meta Ads integration...")

        try:
            oauth_data = self.client.meta.start_connect(redirect_uri=redirect_uri)
        except (NetworkError, ValidationError) as exc:
            print(f"❌ Failed to start Meta OAuth flow: {exc}")
            return

        authorization_url = oauth_data["authorization_url"]
        state = oauth_data.get("state")

        print("\n🔗 Open this URL to grant access:")
        print(f"   {authorization_url}")

        if auto_browser:
            try:
                webbrowser.open(authorization_url)
                print("✅ Browser opened. Complete the authorization then return here.")
            except Exception:
                print("⚠️ Could not open browser automatically. Please copy the URL manually.")

        print(
            "\nAfter approving the app, you'll land on your redirect URL. "
            "Paste the full URL (or the query string) below so we can finish the setup."
        )
        callback_input = input("Callback URL or code: ").strip()

        if not callback_input:
            print("❌ No data provided. Cancelling setup.")
            return

        code, returned_state, error = parse_callback_url(callback_input)

        if error:
            print(f"❌ {error}")
            return

        if not code:
            # Treat raw input as authorization code fallback
            code = callback_input

        if not returned_state:
            returned_state = state

        if not returned_state:
            print("❌ Missing state token. Please restart the authorization flow.")
            return

        print("\n🔄 Completing Meta Ads integration...")
        try:
            result = self.client.meta.finish_connect(
                code=code,
                state=returned_state,
                redirect_uri=redirect_uri,
            )
        except (AuthenticationError, NetworkError, OAuthError, ValidationError) as exc:
            print(f"❌ Meta connection failed: {exc}")
            return

        self._show_success_message(result)

    def show_status(self) -> None:
        """Display current Meta Ads integration status."""
        print("📊 Meta Ads Integration Status")
        print("=" * 34)

        try:
            status = self.client.meta.get_status()
        except (AuthenticationError, NetworkError) as exc:
            print(f"❌ Unable to retrieve status: {exc}")
            return

        if not status.get("has_integration"):
            print("⚠️ No Meta Ads integration found.")
            return

        print("✅ Status: Connected")
        integration_id = status.get("integration_id")
        if integration_id:
            print(f"   Integration ID: {integration_id}")

        status_label = status.get("status")
        if status_label:
            print(f"   State: {status_label}")

        scopes = status.get("scopes") or []
        if scopes:
            print(f"   Scopes: {', '.join(scopes)}")

        created_at = status.get("created_at")
        if created_at:
            print(f"   Connected: {created_at}")

        updated_at = status.get("updated_at")
        if updated_at and updated_at != created_at:
            print(f"   Updated: {updated_at}")

        metadata = status.get("metadata") or {}
        business_id = metadata.get("business_id")
        if business_id:
            print(f"   Business ID: {business_id}")

    def disconnect_interactive(self) -> None:
        """Remove Meta Ads integration."""
        confirm = input("Are you sure you want to disconnect Meta Ads? (y/N): ").strip().lower()
        if confirm not in {"y", "yes"}:
            print("👋 Cancelled.")
            return

        try:
            response = self.client.meta.disconnect()
        except (AuthenticationError, NetworkError, ValidationError) as exc:
            print(f"❌ Failed to disconnect: {exc}")
            return

        if response.get("success"):
            print("🗑️  Meta Ads integration removed successfully.")
        else:
            print("⚠️ Received unexpected response from server.")

    def _show_success_message(self, result: dict) -> None:
        """Display success details after completing OAuth flow."""
        print("\n🎉 Meta Ads connected successfully!")
        print(f"✅ {result.get('message', 'Integration created successfully')}")

        integration_id = result.get("integration_id")
        if integration_id:
            print(f"   Integration ID: {integration_id}")

        scopes = result.get("scopes") or []
        if scopes:
            print(f"   Scopes: {', '.join(scopes)}")

        print("\n🚀 You can now manage Meta Ads-powered agents with m8tes.")
