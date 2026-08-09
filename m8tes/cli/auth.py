"""
Authentication CLI commands for m8tes SDK.

Provides commands for user registration, login, and token management.

Session auth (login/register/logout/refresh) is the one CLI surface that stays
on /api/v1 — it is browser/JWT-shaped and an API customer never touches it.
Everything else the CLI does goes through the v2 SDK client.
"""

import os
from typing import TYPE_CHECKING, Optional

from .._exceptions import AuthenticationError as V2AuthenticationError
from ..auth.auth import AuthService
from ..auth.credentials import CredentialManager
from ..auth.http import HTTPClient as SessionHTTPClient
from ..exceptions import AuthenticationError
from .prompt import confirm_prompt, prompt
from .validation import prompt_email, prompt_password, prompt_password_confirm

if TYPE_CHECKING:
    from .._client import M8tes

# Bare host default — session-auth paths include /api/v1.
_DEFAULT_PLATFORM_URL = "https://api.m8tes.ai"


class AuthCLI:
    """CLI for authentication management."""

    def __init__(
        self,
        client: Optional["M8tes"] = None,
        base_url: str | None = None,
        profile: str = "default",
    ):
        """
        Initialize Auth CLI.

        Args:
            client: Optional v2 SDK client (used only for key fallbacks)
            base_url: Platform base URL (bare host, no /api suffix)
            profile: Profile name for multi-account support
        """
        self.client = client
        self.base_url = base_url
        self.profile = profile
        self.credentials = CredentialManager(profile=profile)

    def _platform_url(self) -> str:
        """Resolve the bare platform host for session-auth requests.

        Normalized so BOTH env shapes work: a /api/v2-suffixed M8TES_BASE_URL
        (the v2 SDK's documented form) would otherwise double up into
        /api/v2/api/v1/… on this surface.
        """
        from .v2 import normalize_platform_base_url

        return (
            normalize_platform_base_url(self.base_url or os.getenv("M8TES_BASE_URL"))
            or _DEFAULT_PLATFORM_URL
        )

    def _session_service(
        self, api_key: str | None = None, *, profile_bound: bool = False
    ) -> AuthService:
        """Build an AuthService over the session-auth transport.

        `profile_bound` must be True only when `api_key` came from the credential
        store — it is what allows the transport's refresh middleware to run.
        """
        http = SessionHTTPClient(
            base_url=self._platform_url(),
            api_key=api_key,
            profile=self.profile,
            profile_bound=profile_bound,
        )
        return AuthService(http)

    def get_saved_api_key(self) -> str | None:
        """Get saved API key from keychain."""
        return self.credentials.get_api_key()

    def get_valid_api_key(self) -> str | None:
        """Get the saved API key, refreshing an expired session token first.

        Session logins store a JWT access token that expires. The stored key is
        deleted ONLY when the refresh endpoint definitively rejects the refresh
        token (401/403) — every uncertain outcome (no expiry metadata, no
        refresh token, network failure, 5xx) returns the key untouched and lets
        the actual request fail naturally. Deleting on uncertainty logged users
        out on a fresh registration and on any offline moment.
        """
        import requests

        api_key = self.credentials.get_api_key()
        if not api_key or not self.credentials.is_access_token_expired():
            return api_key

        refresh_token = self.credentials.get_refresh_token()
        if not refresh_token:
            return api_key

        try:
            response = requests.post(
                f"{self._platform_url()}/api/v1/auth/refresh",
                json={"refresh_token": refresh_token},
                timeout=15,
                headers={"Content-Type": "application/json"},
            )
        except requests.RequestException:
            return api_key

        # A response we cannot parse as JSON is not evidence about the token —
        # a proxy or wrong service can answer any status with HTML. Treat it as
        # uncertain (key untouched) whatever the status code.
        try:
            data = response.json()
        except ValueError:
            return api_key

        if response.status_code == 200:
            new_key: str | None = data.get("api_key")
            if new_key:
                self.credentials.save_api_key(new_key)
                self.credentials.save_token_metadata(
                    refresh_token=data.get("refresh_token"),
                    access_expiration=data.get("access_expires_at"),
                    refresh_expiration=data.get("refresh_expires_at"),
                )
                return new_key
            return api_key
        if response.status_code in (401, 403):
            self.credentials.delete_api_key()
            return None
        return api_key

    def _probe_v2_key(self, api_key: str) -> bool:
        """Validate an API key against the v2 API; returns the email-verified state.

        Raises the v2 AuthenticationError for an invalid/revoked key. The legacy
        /api/v1 user endpoint is JWT-only, so it can never validate an m8_ key.
        """
        from .._client import M8tes as V2Client
        from .v2 import normalize_v2_base_url

        # Route through the resolved platform host so a bare-host M8TES_BASE_URL
        # is normalized here too (passing None would let M8tes consume the raw env).
        v2 = V2Client(api_key=api_key, base_url=normalize_v2_base_url(self._platform_url()))
        try:
            return v2.auth.is_verified()
        finally:
            v2.close()

    def get_current_account_info(self) -> dict | None:
        """
        Get current authenticated account information if available.

        Returns:
            Dict with account info if authenticated, None otherwise
        """
        # Check for saved credentials
        saved_api_key = self.credentials.get_api_key()
        profile_info = self.credentials.get_profile_info()

        if not saved_api_key:
            return None

        try:
            # Validate against the v2 API (the legacy /api/v1 user endpoint is
            # JWT-only and would read every m8_ key as invalid).
            verified = self._probe_v2_key(saved_api_key)
            return {
                "email": profile_info.get("email", "Unknown"),
                "profile": self.profile,
                "verified": verified,
                "has_api_key": True,
            }
        except Exception:
            # If we can't validate but have saved credentials, return what we know
            return {
                "email": profile_info.get("email", "Unknown"),
                "profile": self.profile,
                "has_api_key": True,
                "error": "Cannot verify account (credentials may be expired)",
            }

    def register_interactive(self) -> None:
        """Interactive user registration."""
        print("🚀 M8tes User Registration")
        print("=" * 30)

        # Check if user already has saved credentials
        current_account = self.get_current_account_info()
        if current_account:
            print("\n⚠️  You already have saved credentials:")
            print(f"   Email: {current_account['email']}")
            print(f"   Profile: {current_account['profile']}")
            if "error" in current_account:
                print(f"   Status: {current_account['error']}")

            if not confirm_prompt("Do you want to replace these credentials with a new account?"):
                print("Registration cancelled.")
                return

        # Get email with validation
        email = prompt_email("📧 Email address: ")

        # Get password with validation and confirmation
        password = prompt_password_confirm("🔐 Password (min 8 characters): ")

        # Required first name
        first_name = prompt("👤 First name: ", allow_empty=False)

        print("\n🔄 Creating account...")

        # Session-auth request (failures raise; the command layer maps
        # them to a friendly message and a non-zero exit code)
        result = self._session_service().register_user(
            email=email,
            password=password,
            first_name=first_name,
        )

        print("\n✅ Registration successful!")
        print(f"   User ID: {result.get('user', {}).get('id')}")
        print(f"   Email: {result.get('user', {}).get('email')}")

        # Save the API key if provided (should be included now)
        api_key = result.get("api_key")
        if api_key:
            if self.credentials.save_api_key(api_key):
                # Expiry metadata must land with the key: a key stored without it
                # reads as "expired" to the refresh path on the very next command.
                self.credentials.save_token_metadata(
                    refresh_token=result.get("refresh_token"),
                    access_expiration=result.get("access_expires_at"),
                    refresh_expiration=result.get("refresh_expires_at"),
                )
                storage_type = (
                    "OS keychain" if self.credentials.is_keyring_available else "local config"
                )
                print(f"   🔐 Token saved to {storage_type}")
                print("   You can now use m8tes commands without re-authenticating")
            else:
                print("   ⚠️  Failed to save token. You may need to re-authenticate later.")

        # Save profile info (email) to config
        user_email = result.get("user", {}).get("email", email)
        self.credentials.save_profile_info(email=user_email, base_url=self.base_url)

        # Show next steps
        if api_key:
            self._show_getting_started_guide()
        else:
            print("\n💡 Next step: Login with 'm8tes auth login'")

    def login_interactive(self, save_token: bool = True) -> None:
        """
        Interactive user login.

        Args:
            save_token: Whether to save the token to config file
        """
        print("🔐 M8tes Login")
        print("=" * 20)

        # Check if user already has saved credentials
        current_account = self.get_current_account_info()
        current_email = None
        if current_account:
            current_email = current_account["email"]
            print(f"\n⚠️  You already have saved credentials for: {current_email}")
            print(f"   Profile: {current_account['profile']}")
            if "error" in current_account:
                print(f"   Status: {current_account['error']}")
            print()  # Extra line for readability

        # Get email with validation
        email = prompt_email("📧 Email: ")

        # If logging in as different user, ask for confirmation
        if current_account and current_email and current_email.lower() != email.lower():
            print("\n⚠️  You are logging in as a different user:")
            print(f"   Current: {current_email}")
            print(f"   New: {email}")
            if not confirm_prompt("This will replace your current session. Continue?"):
                print("Login cancelled.")
                return

        # Get password with validation
        password = prompt_password("🔑 Password: ")

        print("\n🔄 Authenticating...")

        # Session-auth request (failures raise; the command layer maps
        # them to a friendly message and a non-zero exit code)
        login_response = self._session_service().login(email=email, password=password)

        api_key = login_response.get("api_key") if login_response else None
        if not api_key:
            raise AuthenticationError("No API key returned")

        print("\n✅ Login successful!")

        if save_token:
            # Save the API key to keychain
            if self.credentials.save_api_key(api_key):
                storage_type = (
                    "OS keychain" if self.credentials.is_keyring_available else "local config"
                )
                print(f"   🔐 Token saved to {storage_type}")
                print("   You can now use m8tes commands without re-authenticating")

                # Save profile info (email) to config file
                self.credentials.save_profile_info(email=email, base_url=self.base_url)

                # Save token metadata
                self.credentials.save_token_metadata(
                    refresh_token=login_response.get("refresh_token"),
                    access_expiration=login_response.get("access_expires_at"),
                    refresh_expiration=login_response.get("refresh_expires_at"),
                )
            else:
                print("   ⚠️  Failed to save token. You may need to re-authenticate later.")
        else:
            print(f"   API Key: {api_key}")
            print("   Set this as M8TES_API_KEY environment variable")

        # Show next steps
        self._show_getting_started_guide()

    def show_status(self) -> None:
        """Show current authentication status."""
        print(f"👤 Authentication Status (Profile: {self.profile})")
        print("=" * 40)

        # Check for saved token in keychain
        saved_api_key = self.credentials.get_api_key()
        if saved_api_key:
            storage_type = (
                "OS keychain" if self.credentials.is_keyring_available else "local config"
            )
            print(f"✅ Saved credentials found ({storage_type})")
            print(f"   Profile: {self.profile}")
        else:
            print("❌ No saved credentials")

        # Check environment variable
        env_api_key = os.getenv("M8TES_API_KEY")
        if env_api_key:
            print("✅ Environment variable set: M8TES_API_KEY")

        # Show keyring availability
        if not self.credentials.is_keyring_available:
            print("⚠️  Keyring not available - credentials stored in plain text")
            print("   Install keyring for secure storage: pip install keyring")

        # Validate the key against the v2 API. The legacy /api/v1 user endpoint is
        # JWT-only, so probing it with an m8_ API key always read as "invalid" —
        # and used to wipe the saved keychain token on that false positive. A
        # status command must never mutate credentials.
        active_api_key = saved_api_key or env_api_key or getattr(self.client, "api_key", None)
        if active_api_key:
            print("\n🔄 Checking API key...")
            try:
                verified = self._probe_v2_key(active_api_key)
                print("\n✅ API key is valid")
                email = self.credentials.get_profile_info().get("email")
                if email:
                    print(f"   Email: {email}")
                if verified:
                    print("   Email verified: yes")
                else:
                    print("   Email verified: no — run 'm8tes auth resend-verify'")
            except V2AuthenticationError:
                print("⚠️  API key is invalid or revoked")
                print("   Run 'm8tes auth login' to refresh your credentials")
                print("   Run 'm8tes auth register' to register a new account")
            except Exception as e:
                print(f"⚠️  Could not verify API key: {e}")
        else:
            print("\n💡 Run 'm8tes auth login' to authenticate")

    def logout_interactive(self) -> None:
        """Interactive logout (clear saved credentials)."""
        print("🚪 Logout")
        print("=" * 10)

        # Check if we have any credentials to clear
        saved_api_key = self.credentials.get_api_key()

        if not saved_api_key:
            print("ℹ️  No saved credentials to clear")  # noqa: RUF001
            return

        # Optionally invalidate token on server. The ACTIVE credential wins
        # (an explicit --api-key / client key over the saved one): revoking the
        # saved session while an explicitly selected key stays live logs out
        # the wrong session.
        api_key_to_use = getattr(self.client, "api_key", None) or saved_api_key
        try:
            print("🔄 Invalidating token on server...")
            service = self._session_service(
                api_key=api_key_to_use,
                # Comparing what we already hold — no extra credential read.
                profile_bound=api_key_to_use == saved_api_key,
            )
            if service.logout():
                print("✅ Token invalidated on server")
        except Exception as e:
            print(f"⚠️  Could not invalidate token: {e}")

        # Clear local credentials
        if self.credentials.clear_profile():
            print("✅ Local credentials cleared")
        else:
            print("⚠️  Some credentials may not have been cleared completely")

        print("   You will need to login again to use authenticated commands")

    def _show_getting_started_guide(self) -> None:
        """Show getting started guide after successful authentication."""
        print("\n" + "=" * 60)
        print("🚀 Getting Started with M8tes")
        print("=" * 60)

        print("\n📋 Next Steps:")
        print("\n1️⃣  Create your first agent:")
        print("   m8tes agent create")

        print("\n2️⃣  Run a task with your agent:")
        print('   m8tes agent task <agent-id> "Your task here"')

        print("\n3️⃣  Start an interactive chat session:")
        print("   m8tes agent chat <agent-id>")

        print("\n📚 For more help:")
        print("   m8tes --help")
        print()
