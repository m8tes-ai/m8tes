"""HTTP client with retry logic and session management."""

from typing import TYPE_CHECKING, Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..exceptions import (
    AuthenticationError,
    NetworkError,
    OAuthError,
    RateLimitError,
    TimeoutError,
    ValidationError,
)

if TYPE_CHECKING:
    from ..client import M8tes


class HTTPClient:
    """HTTP client with built-in retry strategy and error handling."""

    # mypy: disable-error-code="no-any-return,union-attr"
    def __init__(
        self,
        base_url: str,
        api_key: str | None = None,
        timeout: int = 30,
        profile: str = "default",
    ):
        """
        Initialize HTTP client.

        Args:
            base_url: Base URL for all requests
            api_key: Optional API key for authentication
            timeout: Request timeout in seconds
            profile: Profile name for credential management
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout
        self.profile = profile
        self._session: requests.Session | None = None
        self.client: M8tes  # Set by M8tes.__init__ for circular access

        # Initialize HTTP session immediately for backward compatibility
        self._init_session()

    def set_api_key(self, api_key: str) -> None:
        """Update the API key and refresh session headers."""
        self.api_key = api_key
        if self._session and api_key:
            self._session.headers["Authorization"] = f"Bearer {api_key}"

    def _init_session(self) -> None:
        """Initialize HTTP session with retry strategy."""
        if self._session is not None:
            return

        self._session = requests.Session()

        # Configure retry strategy
        # Bug #13 fix: Remove POST from allowed_methods - POST is not idempotent
        # and auto-retrying could create duplicate records
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        self._session.mount("http://", adapter)
        self._session.mount("https://", adapter)

        # Set default headers
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "m8tes-python-sdk/0.1.0",
        }

        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        self._session.headers.update(headers)

    def request(
        self,
        method: str,
        path: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        auth_required: bool = True,
    ) -> dict[str, Any]:
        """
        Make HTTP request with error handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            path: API endpoint path
            json_data: JSON data for request body
            params: Query parameters
            auth_required: Whether authentication is required

        Returns:
            Response data as dictionary

        Raises:
            AuthenticationError: For authentication failures
            ValidationError: For validation errors
            RateLimitError: For rate limit errors
            NetworkError: For network errors
            TimeoutError: For request timeouts
            OAuthError: For OAuth-specific errors
        """
        self._init_session()

        url = f"{self.base_url}{path}"

        # For unauthenticated requests, make a simple request without auth logic
        if not auth_required:
            try:
                # Make request without Authorization header
                response = requests.request(
                    method=method,
                    url=url,
                    json=json_data,
                    params=params,
                    timeout=self.timeout,
                    headers={
                        "Content-Type": "application/json",
                        "User-Agent": "m8tes-python-sdk/0.1.0",
                    },
                )
            except requests.Timeout as e:
                raise TimeoutError(f"Request to {url} timed out after {self.timeout}s") from e
            except requests.RequestException as e:
                raise NetworkError(f"Network error: {e!s}") from e

            # For unauthenticated requests, handle errors and return
            # Don't interpret 401 as auth token issues - it means invalid login credentials
            if response.status_code == 404:
                raise ValidationError("Resource not found", code="not_found")
            elif response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                raise RateLimitError(
                    "Rate limit exceeded. Please try again later.",
                    retry_after=retry_after,
                    code="rate_limit_exceeded",
                )
            elif 400 <= response.status_code < 500:
                # Parse error response
                try:
                    error_data = response.json()
                    if "error" in error_data or "message" in error_data:
                        error_msg = error_data.get("message") or error_data.get(
                            "error", "Request failed"
                        )
                        raise ValidationError(
                            error_msg,
                            code=error_data.get("code", "validation_error"),
                            details=error_data,
                        )
                except (ValueError, KeyError):
                    pass
                raise ValidationError(
                    f"Request failed with status {response.status_code}", code="validation_error"
                )
            elif response.status_code >= 500:
                try:
                    error_data = response.json()
                    if "error" in error_data:
                        raise NetworkError(
                            error_data.get("error", "Server error"),
                            code="server_error",
                            details=error_data,
                        )
                except (ValueError, KeyError, TypeError):
                    pass
                raise NetworkError("Server error. Please try again later.", code="server_error")

            # Success - return response data
            try:
                return response.json()  # type: ignore[no-any-return]
            except ValueError as e:
                if 200 <= response.status_code < 300:
                    return {"success": True}
                raise NetworkError(
                    "Invalid JSON response from server", code="invalid_response"
                ) from e

        else:
            # Authenticated request - check if we have credentials
            if not self.api_key:
                raise AuthenticationError(
                    "Not authenticated. Please login first with 'm8tes auth login' or set "
                    "M8TES_API_KEY environment variable.",
                    code="no_credentials",
                )

            # Proactively refresh token if needed
            self._ensure_valid_token()

            try:
                response = self._session.request(  # type: ignore[union-attr]
                    method=method,
                    url=url,
                    json=json_data,
                    params=params,
                    timeout=self.timeout,
                )
            except requests.Timeout as e:
                raise TimeoutError(f"Request to {url} timed out after {self.timeout}s") from e
            except requests.RequestException as e:
                raise NetworkError(f"Network error: {e!s}") from e

            # Check if response looks like it's from the m8tes API
            content_type = response.headers.get("Content-Type", "")
            server_header = response.headers.get("Server", "")

            # Detect if we're connecting to wrong service (e.g., AirPlay Receiver on port 5000)
            if "AirTunes" in server_header or (
                response.status_code in [401, 403] and "application/json" not in content_type
            ):
                raise NetworkError(
                    f"Cannot connect to m8tes API at {self.base_url}. "
                    "Check that:\n"
                    "  • The backend server is running\n"
                    "  • You're using the correct URL/port\n"
                    f"  • Current URL: {url}\n"
                    "Hint: Use --base-url flag to specify a different URL",
                    code="wrong_service",
                )

            # Handle 401 - try token refresh
            if response.status_code == 401:
                if self._try_refresh_token():
                    # Retry the request with the new token
                    response = self._session.request(  # type: ignore[union-attr]
                        method=method,
                        url=url,
                        json=json_data,
                        params=params,
                        timeout=self.timeout,
                    )
                    if response.status_code == 401:
                        raise AuthenticationError.invalid_api_key()
                else:
                    raise AuthenticationError.invalid_api_key()

        # Common error handling for all requests
        if response.status_code == 401:
            raise AuthenticationError.invalid_api_key()
        elif response.status_code == 403:
            # Parse 403 to distinguish between auth and permission issues
            try:
                error_data = response.json()
                detail = error_data.get("detail", "")

                # "Not authenticated" means auth problem (bad/missing token)
                if "not authenticated" in detail.lower():
                    raise AuthenticationError(
                        "Not authenticated. Your credentials may have expired. "
                        "Please login again with 'm8tes auth login'",
                        code="authentication_required",
                    )
                # "Access denied" or other messages mean permission problem
                else:
                    raise ValidationError(detail or "Access denied", code="access_denied")
            except (ValueError, KeyError) as e:
                # If can't parse, treat as auth error (safer default)
                raise AuthenticationError(
                    "Authentication failed. Please login again with 'm8tes auth login'",
                    code="authentication_required",
                ) from e
        elif response.status_code == 404:
            raise ValidationError("Resource not found", code="not_found")
        elif response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            raise RateLimitError(
                "Rate limit exceeded. Please try again later.",
                retry_after=retry_after,
                code="rate_limit_exceeded",
            )
        elif 400 <= response.status_code < 500:
            # Try to parse error response
            try:
                error_data = response.json()
                if "error" in error_data or "message" in error_data:
                    # Get error message from "message" or "error" field
                    # (prefer message for user-facing errors)
                    error_msg = error_data.get("message") or error_data.get(
                        "error", "Request validation failed"
                    )

                    if "oauth" in str(error_msg).lower():
                        raise OAuthError(
                            error_msg,
                            code=error_data.get("code", "oauth_error"),
                            details=error_data,
                        )
                    raise ValidationError(
                        error_msg,
                        code=error_data.get("code", "validation_error"),
                        details=error_data,
                    )
            except (ValueError, KeyError):
                pass

            raise ValidationError(
                f"Request failed with status {response.status_code}", code="validation_error"
            )
        elif response.status_code >= 500:
            # Try to parse error response for better error messages
            try:
                error_data = response.json()
                if "error" in error_data:
                    raise NetworkError(
                        error_data.get("error", "Server error. Please try again later."),
                        code="server_error",
                        details=error_data,
                    )
            except (ValueError, KeyError, TypeError):
                pass

            raise NetworkError("Server error. Please try again later.", code="server_error")

        # Parse JSON response for successful requests
        try:
            return response.json()  # type: ignore[no-any-return]
        except ValueError as e:
            # If no JSON, return empty dict for successful requests
            if 200 <= response.status_code < 300:
                return {"success": True}
            raise NetworkError("Invalid JSON response from server", code="invalid_response") from e

    def get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        auth_required: bool = True,
    ) -> dict[str, Any]:
        """Make GET request."""
        return self.request("GET", path, params=params, auth_required=auth_required)

    def post(
        self,
        path: str,
        json_data: dict[str, Any] | None = None,
        auth_required: bool = True,
    ) -> dict[str, Any]:
        """Make POST request."""
        return self.request("POST", path, json_data=json_data, auth_required=auth_required)

    def put(
        self,
        path: str,
        json_data: dict[str, Any] | None = None,
        auth_required: bool = True,
    ) -> dict[str, Any]:
        """Make PUT request."""
        return self.request("PUT", path, json_data=json_data, auth_required=auth_required)

    def delete(
        self,
        path: str,
        auth_required: bool = True,
    ) -> dict[str, Any]:
        """Make DELETE request."""
        return self.request("DELETE", path, auth_required=auth_required)

    def _ensure_valid_token(self) -> None:
        """
        Ensure we have a valid access token, refreshing if needed.
        """
        try:
            from ..auth.credentials import CredentialManager

            credentials = CredentialManager(profile=self.profile)

            # Check if current token is expired or expires soon
            if credentials.is_access_token_expired():
                # Try to refresh the token
                self._try_refresh_token()
        except Exception:
            # If anything fails, just continue with existing token
            pass

    def _try_refresh_token(self) -> bool:
        """
        Try to refresh the access token using saved credentials.

        Returns:
            True if token was refreshed successfully, False otherwise
        """
        try:
            from ..auth.credentials import CredentialManager

            credentials = CredentialManager(profile=self.profile)
            refresh_token = credentials.get_refresh_token()

            if not refresh_token:
                return False

            # Make refresh request without authorization header
            refresh_response = self._session.request(  # type: ignore[union-attr]
                method="POST",
                url=f"{self.base_url}/api/v1/auth/refresh",
                json={"refresh_token": refresh_token},
                timeout=self.timeout,
                headers={"Authorization": ""},
            )

            if refresh_response.status_code == 200:
                data = refresh_response.json()
                new_api_key = data.get("api_key")

                if new_api_key:
                    # Update the API key and session headers
                    self.set_api_key(new_api_key)

                    # Save the new token
                    credentials.save_api_key(new_api_key)

                    # Save token metadata if provided
                    credentials.save_token_metadata(
                        refresh_token=data.get("refresh_token"),
                        access_expiration=data.get("access_expires_at"),
                        refresh_expiration=data.get("refresh_expires_at"),
                    )

                    return True

            return False

        except Exception:
            # If refresh fails for any reason, return False
            return False

    def close(self) -> None:
        """Close the session."""
        if self._session:
            self._session.close()
            self._session = None
