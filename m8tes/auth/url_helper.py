"""Helper functions for parsing OAuth callback URLs."""

import urllib.parse


def parse_callback_url(url: str) -> tuple[str | None, str | None, str | None]:
    """
    Parse a callback URL to extract code and state parameters.

    Args:
        url: The full callback URL or just the query parameters

    Returns:
        Tuple of (code, state, error_message)
    """
    try:
        # Handle different input formats
        if url.startswith("http"):
            # Full URL
            parsed = urllib.parse.urlparse(url)
            query = parsed.query
        elif url.startswith("?"):
            # Query string starting with ?
            query = url[1:]
        elif "=" in url:
            # Raw query string
            query = url
        else:
            return None, None, "Invalid URL format"

        # Parse query parameters
        params = urllib.parse.parse_qs(query)

        # Extract code and state
        code = params.get("code", [None])[0]
        state = params.get("state", [None])[0]
        error = params.get("error", [None])[0]

        if error:
            error_desc = params.get("error_description", [error])[0]
            return None, None, f"OAuth error: {error} - {error_desc}"

        if not code:
            return None, None, "No authorization code found in URL"

        return code, state, None

    except Exception as e:
        return None, None, f"Error parsing URL: {e!s}"


def extract_from_browser_url(
    prompt_text: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    """
    Interactive helper to get authorization code from user input.

    Accepts various formats automatically:
    - Full callback URL
    - Just the authorization code
    - Query parameters

    Returns:
        Tuple of (code, state, error_message)
    """
    if not prompt_text:
        prompt_text = "Enter the authorization code: "

    user_input = input(prompt_text).strip()

    if not user_input:
        return None, None, "No input provided"

    # Try to parse as URL first
    code, state, error = parse_callback_url(user_input)

    if code:
        return code, state, error

    # If that failed, assume it's just the authorization code
    if user_input.startswith("4/") or user_input.startswith("1//"):
        # Looks like a Google authorization code
        return user_input, None, None

    return None, None, f"Invalid authorization code format: {user_input[:30]}..."


def validate_authorization_code(code: str) -> bool:
    """
    Basic validation of authorization code format.

    Args:
        code: The authorization code to validate

    Returns:
        True if the code looks valid
    """
    if not code:
        return False

    # Google authorization codes typically start with specific prefixes
    # and are fairly long
    if len(code) < 20:
        return False

    # Common Google auth code prefixes
    valid_prefixes = ["4/", "1//"]

    return any(code.startswith(prefix) for prefix in valid_prefixes)
