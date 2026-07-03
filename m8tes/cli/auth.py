"""
Authentication CLI commands for m8tes SDK.

Provides commands for user registration, login, and token management.
"""

import os
from typing import TYPE_CHECKING, Optional

from .._exceptions import AuthenticationError as V2AuthenticationError
from ..auth.credentials import CredentialManager
from ..exceptions import AuthenticationError
from .prompt import confirm_prompt, prompt
from .validation import prompt_email, prompt_password, prompt_password_confirm

if TYPE_CHECKING:
    from ..client import M8tes


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
            client: Optional M8tes client instance
            base_url: Base URL to use for temporary clients when client is None
            profile: Profile name for multi-account support
        """
        self.client = client
        self.base_url = base_url
        self.profile = profile
        self.credentials = CredentialManager(profile=profile)

    def get_saved_api_key(self) -> str | None:
        """Get saved API key from keychain."""
        return self.credentials.get_api_key()

    def _probe_v2_key(self, api_key: str) -> bool:
        """Validate an API key against the v2 API; returns the email-verified state.

        Raises the v2 AuthenticationError for an invalid/revoked key. The legacy
        /api/v1 user endpoint is JWT-only, so it can never validate an m8_ key.
        """
        from .._client import M8tes as V2Client
        from .v2 import normalize_v2_base_url

        v2 = V2Client(api_key=api_key, base_url=normalize_v2_base_url(self.base_url))
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

        # Use the client to register (failures raise; the command layer maps
        # them to a friendly message and a non-zero exit code)
        if self.client:
            result = self.client.register_user(
                email=email,
                password=password,
                first_name=first_name,
            )
        else:
            # Create temporary client without API key for registration
            from ..client import M8tes

            temp_client = M8tes(api_key=None, base_url=self.base_url)
            result = temp_client.register_user(
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

        # Use the client to login (failures raise; the command layer maps
        # them to a friendly message and a non-zero exit code)
        if self.client:
            login_response = self.client.login(email=email, password=password)
        else:
            # Create temporary client without API key for login
            from ..client import M8tes

            temp_client = M8tes(api_key=None, base_url=self.base_url)
            login_response = temp_client.login(email=email, password=password)

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
        active_api_key = saved_api_key or env_api_key or (self.client and self.client.api_key)
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

        # Optionally invalidate token on server
        api_key_to_use = saved_api_key or (self.client and self.client.api_key)
        if api_key_to_use:
            try:
                print("🔄 Invalidating token on server...")
                if self.client and self.client.api_key:
                    success = self.client.logout()
                else:
                    from ..client import M8tes

                    temp_client = M8tes(api_key=api_key_to_use, base_url=self.base_url)
                    success = temp_client.logout()

                if success:
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
        print("\n1️⃣  Create your first teammate:")
        print("   m8tes mate create")

        print("\n2️⃣  Run a task with your teammate:")
        print('   m8tes mate task <teammate-id> "Your task here"')

        print("\n3️⃣  Start an interactive chat session:")
        print("   m8tes mate chat <teammate-id>")

        print("\n📚 For more help:")
        print("   m8tes --help")
        print()
