"""
Interactive CLI for Google Ads integration.

Provides user-friendly command-line interface for OAuth flow and integration management.
"""

# mypy: disable-error-code="assignment,return-value,no-any-return,attr-defined,arg-type"
from __future__ import annotations

from typing import TYPE_CHECKING
import webbrowser

from ..auth.oauth_flow import run_streamlined_oauth_flow
from ..auth.url_helper import extract_from_browser_url
from ..exceptions import AuthenticationError, NetworkError, OAuthError, ValidationError

if TYPE_CHECKING:
    from ..client import M8tes


class GoogleIntegrationCLI:
    """Interactive CLI for Google Ads integration management."""

    def __init__(self, client: M8tes):
        self.client = client

    def connect_interactive(
        self,
        redirect_uri: str = "http://localhost:8080/callback",
        auto_browser: bool = False,
        use_local_server: bool = True,
        port: int = 8080,
    ) -> None:
        """Interactive Google OAuth connection flow."""
        print("🚀 Setting up Google Ads integration...")

        browser_opened = False

        try:
            status = self._safe_get_status()
            if status and status.get("has_integration"):
                status = self._handle_existing_integration(status)
                reconnect = input("🔄 Reconnect anyway? (y/N): ").strip().lower()
                if reconnect != "y":
                    print("👋 Cancelled.")
                    return
                self._disconnect_current()

            if use_local_server:
                result = self._try_local_server_flow(port, auto_browser)
                if auto_browser:
                    browser_opened = True
                if result:
                    selected = self._ensure_customer_selection(result=result)
                    if selected:
                        result["customer_id"] = selected
                    self._show_success_message(result)
                    return

            result = self._manual_oauth_flow(redirect_uri, auto_browser and not browser_opened)
            if result:
                selected = self._ensure_customer_selection(result=result)
                if selected:
                    result["customer_id"] = selected
                self._show_success_message(result)

        except KeyboardInterrupt:
            print("\n\n👋 Setup cancelled by user")
        except Exception as e:
            print(f"\n❌ Unexpected error: {e}")
            print("💡 Try again or check your API key and network connection")

    def _try_local_server_flow(self, port: int, auto_browser: bool) -> dict:
        """Try the streamlined OAuth flow."""
        return run_streamlined_oauth_flow(client=self.client, port=port, auto_browser=auto_browser)

    def _manual_oauth_flow(self, redirect_uri: str, auto_browser: bool) -> dict | None:
        """Fallback manual OAuth flow."""
        try:
            print("\n🔗 Manual authorization required...")

            try:
                oauth_data = self.client.google.start_connect(
                    redirect_uri=redirect_uri,
                    state=None,
                )
            except Exception as e:
                print(f"❌ Failed to start OAuth: {e}")
                return None

            auth_url = oauth_data["authorization_url"]
            print(f"\nPlease visit: {auth_url}")

            if auto_browser:
                try:
                    webbrowser.open(auth_url)
                    print("✅ Opened in your browser")
                except Exception:
                    pass

            print("\nAfter authorizing, you'll see an authorization code.")
            code, state, error = extract_from_browser_url()

            if error:
                print(f"❌ {error}")
                return None

            if not code:
                print("❌ No authorization code received")
                return None

            if not state:
                state = oauth_data["state"]

            print("🔄 Completing integration...")

            # Get current user ID if authenticated
            user_id = None
            try:
                current_user = self.client.get_current_user()
                user_id = current_user.get("id")
            except Exception:
                # User may not be authenticated yet, that's OK
                pass

            try:
                result = self.client.google.finish_connect(
                    code=code, state=state, redirect_uri=redirect_uri, user_id=user_id
                )
                return result
            except OAuthError as e:
                print(f"❌ OAuth error: {e.message}")
                return None
            except ValidationError:
                print("❌ Invalid authorization code or expired session")
                return None
            except AuthenticationError as e:
                print(f"❌ Authentication failed: {e.message}")
                return None
            except NetworkError as e:
                print(f"❌ Network error: {e.message}")
                return None

        except Exception as e:
            print(f"❌ Authorization failed: {e}")
            return None

    def _show_success_message(self, result: dict) -> None:
        """Show success message after successful OAuth flow."""
        print("\n🎉 Google Ads connected successfully!")
        print(f"✅ {result['message']}")
        print(f"   Integration ID: {result['integration_id']}")

        customer_id = self._normalize_customer_id(result.get("customer_id"))
        if customer_id:
            print(f"   Customer ID: {self._format_customer_id(customer_id)}")
        else:
            available = self._normalize_customer_list(result.get("accessible_customers"))
            if available:
                formatted = ", ".join(self._format_customer_id(cid) for cid in available)
                print(f"   Available customers: {formatted}")

        print("\n🚀 You can now:")
        print("   • Create agents with Google Ads tools")
        print("   • Check status: m8tes google status")
        print("   • Start optimizing your campaigns!")

    def show_status(self) -> None:
        """Show current Google Ads integration status."""
        print("📊 Google Ads Integration Status")
        print("=" * 35)

        try:
            status = self.client.google.get_status()
            has_integration = bool(status.get("has_integration"))

            if has_integration:
                print("✅ Status: Connected")

                integration_id = status.get("integration_id")
                if integration_id:
                    print(f"   Integration ID: {integration_id}")

                status_label = status.get("status")
                if status_label:
                    print(f"   Status: {status_label}")

                scopes = status.get("scopes") or []
                if scopes:
                    print(f"   Scopes: {', '.join(scopes)}")

                customer_id = self._normalize_customer_id(
                    status.get("customer_id") or (status.get("metadata") or {}).get("customer_id")
                )
                if customer_id:
                    print(f"   Customer ID: {self._format_customer_id(customer_id)}")
                else:
                    print("   Customer ID: not set")
                    available = self._normalize_customer_list(status.get("accessible_customers"))
                    if not available:
                        available = self._normalize_customer_list(
                            (status.get("metadata") or {}).get("accessible_customers")
                        )
                    if available:
                        formatted = ", ".join(self._format_customer_id(cid) for cid in available)
                        print(f"   Available customers: {formatted}")

                created = status.get("created_at")
                if created:
                    if isinstance(created, str):
                        print(f"   Connected: {created}")
                    else:
                        print(f"   Connected: {created.isoformat()}")

                updated = status.get("updated_at")
                if updated:
                    if isinstance(updated, str):
                        print(f"   Updated: {updated}")
                    else:
                        print(f"   Updated: {updated.isoformat()}")

                metadata = status.get("metadata") or {}
                if metadata:
                    print("   Metadata:")
                    for key, value in metadata.items():
                        print(f"     {key}: {value}")

            else:
                print("❌ Status: Not Connected")
                print("\n💡 To connect your Google Ads account:")
                print("   m8tes google connect")

        except AuthenticationError:
            print("❌ Authentication required")
            print("💡 Set your API key: export M8TES_API_KEY=your-key")
        except NetworkError as e:
            print(f"❌ Network error: {e.message}")
            print("💡 Check your internet connection and API endpoint")
        except Exception as e:
            print(f"❌ Error checking status: {e}")

    def disconnect_interactive(self) -> None:
        """Interactive Google Ads integration removal."""
        print("🔌 Disconnect Google Ads Integration")
        print("=" * 40)

        try:
            status = self.client.google.get_status()

            if not status.get("has_integration"):
                print("ℹ️  No Google Ads integration found")  # noqa: RUF001
                print("💡 Use 'm8tes google connect' to set up integration")
                return

            print("Current integration:")
            integration_id = status.get("integration_id")
            if integration_id:
                print(f"  Integration ID: {integration_id}")
            status_label = status.get("status") or "unknown"
            print(f"  Status: {status_label}")
            scopes = status.get("scopes") or []
            if scopes:
                print(f"  Scopes: {', '.join(scopes)}")
            customer_id = self._normalize_customer_id(
                status.get("customer_id") or (status.get("metadata") or {}).get("customer_id")
            )
            if customer_id:
                print(f"  Customer ID: {self._format_customer_id(customer_id)}")

            print("\n⚠️  This will permanently remove your Google Ads integration.")
            print("   You'll need to re-authorize to use Google Ads features.")

            confirm = input("\n🔄 Proceed with disconnection? (y/N): ").strip().lower()
            if confirm != "y":
                print("👋 Disconnection cancelled")
                return

            print("\n🔄 Removing integration...")
            try:
                result = self.client.google.disconnect()

                print("\n✅ Google Ads Integration Removed")
                print("-" * 35)
                print(f"✅ {result['message']}")
                print(f"✅ Deleted at: {result['deleted_at']}")

                print("\n💡 To reconnect:")
                print("   m8tes google connect")

            except ValidationError as e:
                if "not_found" in str(e):
                    print("ℹ️  Integration was already removed")  # noqa: RUF001
                else:
                    print(f"❌ {e.message}")
            except Exception as e:
                print(f"❌ Failed to remove integration: {e}")

        except AuthenticationError:
            print("❌ Authentication required")
            print("💡 Set your API key: export M8TES_API_KEY=your-key")
        except NetworkError as e:
            print(f"❌ Network error: {e.message}")
        except Exception as e:
            print(f"❌ Error during disconnection: {e}")

    def _disconnect_current(self) -> None:
        """Helper to disconnect current integration silently."""
        try:
            self.client.google.disconnect()
            print("   Disconnected previous integration")
        except Exception:
            pass

    def _safe_get_status(self) -> dict[str, object] | None:
        try:
            return self.client.google.get_status()
        except AuthenticationError:
            return None
        except NetworkError as e:
            print(f"⚠️  Could not fetch Google Ads status: {e.message}")
            return None
        except Exception as e:
            print(f"⚠️  Could not fetch Google Ads status: {e}")
            return None

    def _handle_existing_integration(self, status: dict[str, object]) -> dict[str, object]:
        current = status or {}
        metadata = current.get("metadata") or {}
        customer_id = self._normalize_customer_id(
            current.get("customer_id") or metadata.get("customer_id")
        )
        status_label = current.get("status") or "connected"

        if customer_id:
            formatted_id = self._format_customer_id(customer_id)
            print(f"✅ Google Ads is already connected (Customer ID: {formatted_id})")
        else:
            print(f"✅ Google Ads is already connected (Status: {status_label})")
            print("ℹ️  No Google Ads customer is selected yet.")  # noqa: RUF001
            selected = self._ensure_customer_selection(status=current)
            if selected:
                print(
                    f"✅ Customer ID {self._format_customer_id(selected)} set for this integration."
                )
            else:
                print("⚠️  Google Ads customer ID is still unset. Some tools may not work.")

        refreshed = self._safe_get_status()
        return refreshed or current

    def _ensure_customer_selection(
        self,
        *,
        status: dict[str, object] | None = None,
        result: dict[str, object] | None = None,
    ) -> str | None:
        status_data = status or {}
        result_data = result or {}
        metadata = status_data.get("metadata") or {}

        integration_id = (
            result_data.get("integration_id")
            or status_data.get("integration_id")
            or metadata.get("integration_id")
        )

        customer_id = (
            self._normalize_customer_id(result_data.get("customer_id"))
            or self._normalize_customer_id(status_data.get("customer_id"))
            or self._normalize_customer_id(metadata.get("customer_id"))
        )

        customers: list[str] = []

        def _extend_customers(values: list[object] | None) -> None:
            for cid in self._normalize_customer_list(values):
                if cid not in customers:
                    customers.append(cid)

        _extend_customers(result_data.get("accessible_customers"))
        _extend_customers(status_data.get("accessible_customers"))
        _extend_customers(metadata.get("accessible_customers"))

        if customer_id:
            if customers and customer_id not in customers:
                print(
                    "⚠️  The stored Google Ads customer no longer appears in the accessible list. "
                    "Please pick a new account to finish setup."
                )
                customer_id = None
            else:
                return customer_id

        if not customers:
            customers, refreshed = self._get_accessible_customers(refresh=False)
            if refreshed and customers:
                print("🔄 Loaded accessible customers from Google Ads.")
        else:
            refreshed = False

        if not customers:
            customers, refreshed = self._get_accessible_customers(refresh=True)
            if refreshed and customers:
                print("🔄 Loaded accessible customers from Google Ads.")

        if not customers:
            manual = self._prompt_manual_customer_id()
            if not manual:
                return None
            saved = self._set_customer_id(manual, integration_id=integration_id)
            if saved:
                print(f"✅ Customer ID {self._format_customer_id(saved)} saved.")
            return saved

        selection = self._prompt_customer_choice(customers)
        if not selection:
            return None

        saved = self._set_customer_id(selection, integration_id=integration_id)
        if saved:
            print(f"✅ Customer ID {self._format_customer_id(saved)} saved.")
        return saved

    def _normalize_customer_list(self, values: list[object] | None) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        if not values:
            return normalized
        for value in values:
            candidate = self._normalize_customer_id(value)
            if candidate and candidate not in seen:
                normalized.append(candidate)
                seen.add(candidate)
        return normalized

    def _get_accessible_customers(self, refresh: bool = False) -> tuple[list[str], bool]:
        try:
            response = self.client.google.list_accessible_customers(refresh=refresh)
        except AuthenticationError as e:
            print(f"❌ Authentication error while loading customers: {e.message}")
            return [], False
        except ValidationError as e:
            print(f"❌ {e.message}")
            return [], False
        except NetworkError as e:
            print(f"❌ Network error while loading customers: {e.message}")
            return [], False
        except Exception as e:
            print(f"⚠️  Could not load accessible customers: {e}")
            return [], False

        customers = self._normalize_customer_list(response.get("accessible_customers"))
        refreshed = bool(response.get("refreshed"))
        return customers, refreshed

    def _prompt_customer_choice(self, customers: list[str]) -> str | None:
        if not customers:
            return None

        print(
            "\n💡 Tip: Account IDs are visible in the top right corner of your Google Ads dashboard"
        )
        print()
        print("👤 Select the Google Ads customer to attach:")
        for idx, cid in enumerate(customers, start=1):
            print(f"   {idx}. {self._format_customer_id(cid)}")

        max_index_digits = len(str(len(customers)))

        while True:
            choice = input("Enter number or customer ID (blank to cancel): ").strip()
            if not choice:
                return None
            if choice.lower() in {"q", "quit", "exit"}:
                return None
            if choice.isdigit() and len(choice) <= max_index_digits:
                index = int(choice)
                if 1 <= index <= len(customers):
                    return customers[index - 1]
                print("❌ Invalid option. Choose a number from the list.")
                continue
            normalized = self._normalize_customer_id(choice)
            if normalized:
                return normalized
            print("❌ Invalid input. Provide a list number or a 10-digit customer ID.")

    def _prompt_manual_customer_id(self) -> str | None:
        print("\nNo accessible Google Ads accounts were returned.")
        print("Enter the customer ID to use (e.g. 123-456-7890) or press Enter to skip.")
        while True:
            value = input("Customer ID: ").strip()
            if not value:
                return None
            normalized = self._normalize_customer_id(value)
            if normalized:
                return normalized
            print("❌ Customer ID must be numeric and between 10 and 20 digits.")

    def _normalize_customer_id(self, value: object) -> str | None:
        if value is None:
            return None
        digits = "".join(ch for ch in str(value) if ch.isdigit())
        if not digits:
            return None
        if len(digits) < 10 or len(digits) > 20:
            return None
        return digits

    def _format_customer_id(self, customer_id: str) -> str:
        if len(customer_id) == 10:
            return f"{customer_id[:3]}-{customer_id[3:6]}-{customer_id[6:]}"
        return customer_id

    def _set_customer_id(
        self, customer_id: str, *, integration_id: int | None = None
    ) -> str | None:
        normalized = self._normalize_customer_id(customer_id)
        if not normalized:
            print("❌ Customer ID must be numeric and at least 10 digits.")
            return None
        try:
            response = self.client.google.set_customer_id(normalized, integration_id=integration_id)
            saved = self._normalize_customer_id(response.get("customer_id")) or normalized
            return saved
        except ValidationError as e:
            print(f"❌ {e.message}")
        except AuthenticationError as e:
            print(f"❌ Authentication error: {e.message}")
        except NetworkError as e:
            print(f"❌ Network error while saving customer ID: {e.message}")
        except Exception as e:
            print(f"❌ Failed to save customer ID: {e}")
        return None
