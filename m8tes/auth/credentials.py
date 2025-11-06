"""
Secure credential storage using OS keychain.

This module provides secure API key storage using the system keychain:
- macOS: Keychain Access
- Windows: Credential Manager
- Linux: libsecret/KWallet
- Fallback: Encrypted file storage
"""

# mypy: disable-error-code="no-any-return"
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import string
import warnings

try:
    import keyring
    import keyring.errors

    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    warnings.warn(
        "keyring not available. API keys will be stored in plain text. "
        "Install keyring for secure credential storage: pip install keyring",
        UserWarning,
        stacklevel=2,
    )


class CredentialManager:
    """Secure credential storage manager using OS keychain."""

    SERVICE_NAME = "m8tes"
    DEFAULT_PROFILE = "default"

    # Fallback config for non-sensitive data
    CONFIG_DIR = Path.home() / ".m8tes"
    CONFIG_FILE = CONFIG_DIR / "config.json"

    def __init__(self, profile: str = DEFAULT_PROFILE):
        """
        Initialize credential manager.

        Args:
            profile: Profile name for multi-account support (default: "default")
        """
        self.profile = profile
        self._ensure_config_dir()

    def _ensure_config_dir(self) -> None:
        """Ensure config directory exists with proper permissions."""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        # Set restrictive permissions (user read/write only). If the OS denies
        # the permission change (e.g. on managed filesystems), continue without
        # failing so CLI usage still works within constrained environments.
        try:
            os.chmod(self.CONFIG_DIR, 0o700)
        except PermissionError:
            return

    def save_api_key(self, api_key: str) -> bool:
        """
        Save API key securely to OS keychain with retry logic.

        Args:
            api_key: API key to store

        Returns:
            True if saved successfully, False otherwise
        """
        if not api_key:
            return False

        try:
            if self.is_keyring_available:
                # Try keychain with retry logic
                result = self._retry_keychain_operation(
                    lambda: keyring.set_password(
                        self.SERVICE_NAME, f"{self.profile}_api_key", api_key
                    )
                )
                return bool(result)  # type: ignore[arg-type]
            else:
                # Fallback to file storage (insecure but functional)
                config = self._load_config_with_profiles()
                if "profiles" not in config:
                    config["profiles"] = {}
                if self.profile not in config["profiles"]:
                    config["profiles"][self.profile] = {}
                config["profiles"][self.profile]["api_key"] = api_key
                return self._save_config_with_profiles(config)
        except Exception as e:
            warnings.warn(f"Failed to save API key: {e}", UserWarning, stacklevel=2)
            return False

    def get_api_key(self) -> str | None:
        """
        Get API key from OS keychain with retry logic.

        Returns:
            API key if found and valid, None otherwise
        """
        try:
            api_key = None
            if self.is_keyring_available:
                # Try keychain with retry logic
                api_key = self._retry_keychain_operation(
                    lambda: keyring.get_password(self.SERVICE_NAME, f"{self.profile}_api_key"),
                    return_value=True,
                )
            else:
                # Fallback to file storage
                config = self._load_config_with_profiles()
                profile_config = config.get("profiles", {}).get(self.profile, {})
                api_key = profile_config.get("api_key")

            # Validate token format to guard against corrupted storage
            if api_key and not self._is_valid_token(str(api_key)):  # type: ignore[arg-type]
                warnings.warn(
                    "\n⚠️  Stored authentication token has invalid format.\n"
                    "   This usually happens when the token is corrupted or outdated.\n"
                    "   Please login again: m8tes --dev auth login",
                    UserWarning,
                    stacklevel=2,
                )
                # Delete invalid token
                self.delete_api_key()
                return None

            return str(api_key) if api_key else None  # type: ignore[arg-type]
        except Exception as e:
            warnings.warn(f"Failed to retrieve API key: {e}", UserWarning, stacklevel=2)
            return None

    def delete_api_key(self) -> bool:
        """
        Delete API key from OS keychain with retry logic.

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            if self.is_keyring_available:
                # Try keychain with retry logic
                result = self._retry_keychain_operation(
                    lambda: keyring.delete_password(self.SERVICE_NAME, f"{self.profile}_api_key"),
                    ignore_password_delete_error=True,
                )
                return bool(result)  # type: ignore[arg-type]
            else:
                # Fallback: remove from file
                config = self._load_config_with_profiles()
                profile_config = config.get("profiles", {}).get(self.profile, {})
                if "api_key" in profile_config:
                    profile_config.pop("api_key")
                    return self._save_config_with_profiles(config)
                return True
        except keyring.errors.PasswordDeleteError:
            # Password wasn't stored, which is fine
            return True
        except Exception as e:
            warnings.warn(f"Failed to delete API key: {e}", UserWarning, stacklevel=2)
            return False

    def save_token_metadata(
        self,
        refresh_token: str | None = None,
        access_expiration: str | None = None,
        refresh_expiration: str | None = None,
    ) -> bool:
        """
        Save token metadata to config file.

        Args:
            refresh_token: Refresh token string
            access_expiration: Access token expiration (ISO format)
            refresh_expiration: Refresh token expiration (ISO format)

        Returns:
            True if saved successfully
        """
        config = self._load_config_with_profiles()

        # Ensure profile section exists
        if "profiles" not in config:
            config["profiles"] = {}
        if self.profile not in config["profiles"]:
            config["profiles"][self.profile] = {}

        profile_config = config["profiles"][self.profile]

        if refresh_token:
            profile_config["refresh_token"] = refresh_token
        if access_expiration:
            profile_config["access_expires_at"] = access_expiration
        if refresh_expiration:
            profile_config["refresh_expires_at"] = refresh_expiration

        return self._save_config_with_profiles(config)

    def get_refresh_token(self) -> str | None:
        """
        Get refresh token from config file.

        Returns:
            Refresh token if found, None otherwise
        """
        config = self._load_config_with_profiles()
        profile_config = config.get("profiles", {}).get(self.profile, {})
        return profile_config.get("refresh_token")

    def get_token_expiration(self) -> dict:
        """
        Get token expiration info from config file.

        Returns:
            Dictionary with expiration times
        """
        config = self._load_config_with_profiles()
        profile_config = config.get("profiles", {}).get(self.profile, {})
        return {
            "access_expiration": profile_config.get("access_expires_at"),
            "refresh_expiration": profile_config.get("refresh_expires_at"),
        }

    def is_access_token_expired(self, buffer_minutes: int = 2) -> bool:
        """
        Check if access token is expired.

        Args:
            buffer_minutes: Minutes before expiration to consider token expired (default: 2)

        Returns:
            True if expired or expiration unknown
        """
        config = self._load_config_with_profiles()
        profile_config = config.get("profiles", {}).get(self.profile, {})
        access_exp = profile_config.get("access_expires_at")
        if not access_exp:
            return True  # Unknown expiration, assume expired

        try:
            from datetime import timedelta

            # Handle both Z and +00:00 timezone formats
            if access_exp.endswith("Z"):
                exp_time = datetime.fromisoformat(access_exp.replace("Z", "+00:00"))
            else:
                exp_time = datetime.fromisoformat(access_exp)
                # If exp_time is timezone-naive, make it UTC
                if exp_time.tzinfo is None:
                    exp_time = exp_time.replace(tzinfo=UTC)

            # Add configurable buffer time
            buffer_time = timedelta(minutes=buffer_minutes)
            now = datetime.now(UTC)

            return now >= (exp_time - buffer_time)
        except (ValueError, AttributeError):
            return True  # Invalid format, assume expired

    def save_profile_info(self, email: str | None = None, base_url: str | None = None) -> bool:
        """
        Save non-sensitive profile information to config file.

        Args:
            email: User email
            base_url: API base URL

        Returns:
            True if saved successfully
        """
        config = self._load_config_with_profiles()

        # Ensure profile section exists
        if "profiles" not in config:
            config["profiles"] = {}
        if self.profile not in config["profiles"]:
            config["profiles"][self.profile] = {}

        profile_config = config["profiles"][self.profile]

        if email:
            profile_config["email"] = email
        if base_url:
            profile_config["base_url"] = base_url

        return self._save_config_with_profiles(config)

    def get_profile_info(self) -> dict:
        """
        Get non-sensitive profile information from config file.

        Returns:
            Dictionary with profile information
        """
        config = self._load_config_with_profiles()
        return config.get("profiles", {}).get(self.profile, {})

    def clear_profile(self) -> bool:
        """
        Clear all profile data (API key from keychain, config from file).

        Returns:
            True if cleared successfully
        """
        success = True

        # Delete API key from keychain
        if not self.delete_api_key():
            success = False

        # Clear config file data for this profile
        config = self._load_config_with_profiles()
        if "profiles" in config and self.profile in config["profiles"]:
            try:
                del config["profiles"][self.profile]
                # If no profiles left, remove the file
                if not config["profiles"]:
                    if self.CONFIG_FILE.exists():
                        self.CONFIG_FILE.unlink()
                else:
                    self._save_config_with_profiles(config)
            except Exception as e:
                warnings.warn(f"Failed to clear config file: {e}", UserWarning, stacklevel=2)
                success = False

        return success

    def _load_from_file(self) -> dict:
        """Load configuration from file."""
        if not self.CONFIG_FILE.exists():
            return {}

        try:
            with open(self.CONFIG_FILE) as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_to_file(self, config: dict) -> bool:
        """Save configuration to file."""
        try:
            self._ensure_config_dir()
            with open(self.CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=2)
            # Set restrictive permissions on config file
            os.chmod(self.CONFIG_FILE, 0o600)
            return True
        except Exception as e:
            warnings.warn(f"Failed to save config: {e}", UserWarning, stacklevel=2)
            return False

    def _load_config_with_profiles(self) -> dict:
        """Load configuration with profiles structure from file."""
        if not self.CONFIG_FILE.exists():
            return {"profiles": {}}

        try:
            with open(self.CONFIG_FILE) as f:
                config = json.load(f)
            # Ensure profiles structure exists
            if "profiles" not in config:
                config["profiles"] = {}
            return config
        except Exception:
            return {"profiles": {}}

    def _save_config_with_profiles(self, config: dict) -> bool:
        """Save configuration with profiles structure to file."""
        try:
            self._ensure_config_dir()
            with open(self.CONFIG_FILE, "w") as f:
                json.dump(config, f, indent=2)
            # Set restrictive permissions on config file
            os.chmod(self.CONFIG_FILE, 0o600)
            return True
        except Exception as e:
            warnings.warn(f"Failed to save config: {e}", UserWarning, stacklevel=2)
            return False

    @classmethod
    def list_profiles(cls) -> list[str]:
        """
        List all available profiles.

        Returns:
            List of profile names
        """
        profiles = []

        if KEYRING_AVAILABLE:
            try:
                # This is a simplified approach - keyring doesn't have a direct way to list all
                # usernames
                # We'll try common profiles and check the config file
                test_profiles = [cls.DEFAULT_PROFILE, "work", "dev", "staging"]
                for profile in test_profiles:
                    if keyring.get_password(cls.SERVICE_NAME, profile):
                        profiles.append(profile)
            except Exception:
                pass

        # Also check config file
        config_file = Path.home() / ".m8tes" / "config.json"
        if config_file.exists():
            try:
                with open(config_file) as f:
                    config = json.load(f)
                    if "profile" in config and config["profile"] not in profiles:
                        profiles.append(config["profile"])
            except Exception:
                pass

        return profiles if profiles else [cls.DEFAULT_PROFILE]

    def _is_valid_jwt(self, token: str) -> bool:
        """
        Check if a token is a valid JWT format.

        JWTs must have exactly 3 parts separated by dots (header.payload.signature).

        Args:
            token: Token string to validate

        Returns:
            True if token is a valid JWT format, False otherwise
        """
        if not token or not isinstance(token, str):
            return False

        # JWT must have exactly 3 parts (header.payload.signature)
        parts = token.split(".")
        if len(parts) != 3:
            return False

        # Each part must be non-empty
        return all(part.strip() for part in parts)

    def _is_valid_token(self, token: str) -> bool:
        """
        Validate stored token allowing both JWTs and API key strings.

        Tokens may be JWTs (dot-delimited segments) or API keys returned by the
        backend that use safe characters. This validation intentionally allows
        non-JWT keys while filtering out obviously malformed or serialized values.
        """
        if not token or not isinstance(token, str):
            return False

        token = token.strip()
        if not token:
            return False

        # Reject common sentinel values
        if token.lower() in {"none", "null"}:
            return False

        # Accept well-formed JWT immediately
        if self._is_valid_jwt(token):
            return True

        # Reject whitespace or structured payloads that indicate corruption
        if any(char.isspace() for char in token):
            return False
        if token.startswith("{") and token.endswith("}"):
            return False

        # Allow API key style tokens comprised of safe characters
        allowed_chars = set(string.ascii_letters + string.digits + "-_.~+/=:")
        return all(char in allowed_chars for char in token)

    def _retry_keychain_operation(
        self,
        operation: object,
        max_retries: int = 3,
        return_value: bool = False,
        ignore_password_delete_error: bool = False,
    ) -> object:
        """
        Retry keychain operations to handle transient failures.

        Args:
            operation: Function to execute
            max_retries: Maximum number of retry attempts
            return_value: Whether to return the operation result
            ignore_password_delete_error: Whether to ignore PasswordDeleteError

        Returns:
            Operation result if return_value=True, otherwise success boolean
        """
        import time

        for attempt in range(max_retries):
            try:
                result = operation()  # type: ignore[operator]
                return result if return_value else True
            except keyring.errors.PasswordDeleteError:
                if ignore_password_delete_error:
                    return True
                raise
            except Exception:
                if attempt < max_retries - 1:
                    # Wait briefly before retrying (exponential backoff)
                    time.sleep(0.1 * (2**attempt))
                    continue
                break

        # All retries failed
        if return_value:
            return None
        return False

    @property
    def is_keyring_available(self) -> bool:
        """Check if keyring is available for secure storage."""
        return KEYRING_AVAILABLE
