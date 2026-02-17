"""Simplified OAuth flow using requests to backend."""

import webbrowser

from .working_server import WorkingOAuthServer


def run_streamlined_oauth_flow(
    client: object, port: int = 8080, auto_browser: bool = True, timeout: int = 300
) -> dict | None:
    """
    Run a streamlined OAuth flow.

        This delegates the OAuth flow to the backend which has better
        infrastructure for handling the local server and OAuth callbacks.

        Args:
            client: M8tes client instance
            port: Preferred port for local server
            auto_browser: Whether to automatically open browser
            timeout: Timeout in seconds

        Returns:
            OAuth result dictionary or None if failed
    """
    try:
        print("\n🔗 Connecting to Google Ads...")

        # Start local callback server
        server = WorkingOAuthServer(port=port)
        _actual_port, redirect_uri = server.start_server()

        # Start OAuth flow with local server
        oauth_data = client.google.start_connect(  # type: ignore[attr-defined]
            redirect_uri=redirect_uri,
            state=None,  # Let backend generate secure state token
        )

        auth_url = oauth_data["authorization_url"]

        # Open browser
        if auto_browser:
            try:
                webbrowser.open(auth_url)
                print("✅ Opened browser for Google authorization")
                print("   Complete the authorization and the integration will finish automatically")
            except Exception:
                print("⚠️  Could not open browser")
                print(f"   Please visit: {auth_url}")
        else:
            print(f"Please visit: {auth_url}")

        print("\n⏳ Waiting for authorization...")

        # Wait for callback
        callback_result = server.wait_for_callback(timeout=timeout)
        server.stop_server()

        if not callback_result.get("success"):
            error = callback_result.get("error", "unknown")
            error_desc = callback_result.get("error_description", "Unknown error")
            print(f"❌ Authorization failed: {error}")
            if error_desc != "Unknown error":
                print(f"   {error_desc}")
            return None

        print("✅ Authorization received, completing integration...")

        # Get current user ID if authenticated
        user_id = None
        try:
            current_user = client.get_current_user()  # type: ignore[attr-defined]
            user_id = current_user.get("id")
        except Exception:
            # User may not be authenticated yet, that's OK
            pass

        # Complete OAuth flow with captured data
        result = client.google.finish_connect(  # type: ignore[attr-defined]
            code=callback_result["code"],
            state=callback_result["state"],  # Use backend's state from callback
            redirect_uri=redirect_uri,
            user_id=user_id,
        )

        return result  # type: ignore[no-any-return]

    except Exception as e:
        print(f"❌ Connection failed: {e}")
        return None
