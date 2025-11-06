"""Working OAuth callback server implementation."""

# ruff: noqa: E501  # Long HTML/CSS lines are acceptable in this file
# mypy: disable-error-code="no-untyped-def,attr-defined,assignment,var-annotated"

from http.server import BaseHTTPRequestHandler, HTTPServer
import socket
import threading
from typing import ClassVar
import urllib.parse


class WorkingOAuthHandler(BaseHTTPRequestHandler):
    """HTTP handler that actually works for OAuth callbacks."""

    # Class variables to store data
    callback_data: ClassVar[dict] = {}
    callback_event: ClassVar[threading.Event | None] = None

    @classmethod
    def set_data(cls, data: dict, event: threading.Event):
        """Set the shared callback data and event."""
        cls.callback_data = data
        cls.callback_event = event

    def do_GET(self):
        """Handle GET requests from OAuth redirect."""
        try:
            # Only handle callback URLs
            if not self.path.startswith("/callback"):
                self._send_404()
                return

            # Parse query parameters
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)

            if "code" in params and "state" in params:
                # Success case
                code = params["code"][0]
                state = params["state"][0]

                self.callback_data["code"] = code
                self.callback_data["state"] = state
                self.callback_data["success"] = True

                # Send success page with FULL code (no truncation)
                self._send_success_page(code, state)

                # Signal completion
                if self.callback_event:
                    self.callback_event.set()

            elif "error" in params:
                # Error case
                error = params["error"][0]
                error_description = params.get("error_description", ["Unknown error"])[0]

                self.callback_data["error"] = error
                self.callback_data["error_description"] = error_description
                self.callback_data["success"] = False

                print(f"❌ OAuth error: {error}")

                self._send_error_page(error, error_description)

                # Signal completion
                if self.callback_event:
                    self.callback_event.set()
            else:
                self._send_400("Missing required parameters")

        except Exception as e:
            print(f"❌ Error handling callback: {e}")
            self._send_500(str(e))

    def _send_success_page(self, code: str, state: str):
        """Send success page with authorization code."""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>M8tes - Authorization Complete</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 500px; margin: 80px auto; padding: 20px; background: #f5f5f5; text-align: center; }}
        .container {{ background: white; padding: 40px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .success {{ color: #4CAF50; font-size: 28px; margin-bottom: 20px; }}
        .message {{ color: #333; font-size: 16px; margin-bottom: 30px; line-height: 1.5; }}
        .code-section {{ background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 8px; padding: 20px; margin: 20px 0; }}
        .code-label {{ color: #666; font-size: 14px; margin-bottom: 10px; }}
        .code {{ font-family: monospace; font-size: 14px; word-break: break-all; background: #e9ecef; padding: 12px; border-radius: 5px; cursor: pointer; line-height: 1.4; }}
        .copy-btn {{ background: #007bff; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; font-size: 14px; margin-top: 10px; }}
        .copy-btn:hover {{ background: #0056b3; }}
        .auto-close {{ color: #999; font-size: 13px; margin-top: 30px; }}
        .fallback {{ color: #666; font-size: 14px; margin-top: 20px; padding: 15px; background: #fff3cd; border-radius: 5px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="success">✅ Authorization Complete!</div>

        <div class="message">
            <strong>Your Google Ads account has been connected.</strong><br>
            The integration should complete automatically.
        </div>

        <div class="fallback">
            <strong>If the CLI doesn't complete automatically:</strong><br>
            Copy the authorization code below and paste it into the terminal.
        </div>

        <div class="code-section">
            <div class="code-label">Authorization Code:</div>
            <div class="code" id="auth-code" onclick="selectText('auth-code')">{code}</div>
            <button class="copy-btn" onclick="copyToClipboard('{code}')">Copy Code</button>
        </div>

        <div class="auto-close">
            This tab will close automatically in <span id="countdown">10</span> seconds.
        </div>
    </div>

    <script>
        function selectText(elementId) {{
            const element = document.getElementById(elementId);
            if (window.getSelection) {{
                const selection = window.getSelection();
                const range = document.createRange();
                range.selectNodeContents(element);
                selection.removeAllRanges();
                selection.addRange(range);
            }}
        }}

        function copyToClipboard(text) {{
            navigator.clipboard.writeText(text).then(function() {{
                const btn = event.target;
                const originalText = btn.textContent;
                btn.textContent = 'Copied!';
                btn.style.background = '#28a745';
                setTimeout(function() {{
                    btn.textContent = originalText;
                    btn.style.background = '#007bff';
                }}, 2000);
            }}, function(err) {{
                console.error('Could not copy text: ', err);
                alert('Could not copy to clipboard. Please select and copy manually.');
            }});
        }}

        // Countdown and auto-close
        let timeLeft = 10;
        const countdownEl = document.getElementById('countdown');

        const timer = setInterval(function() {{
            timeLeft -= 1;
            countdownEl.textContent = timeLeft;

            if (timeLeft <= 0) {{
                clearInterval(timer);
                window.close();
            }}
        }}, 1000);
    </script>
</body>
</html>"""

        self._send_html_response(200, html)

    def _send_error_page(self, error: str, error_description: str):
        """Send error page."""
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>M8tes - OAuth Error</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; background: #f5f5f5; }}
        .container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .error {{ color: #f44336; font-size: 24px; margin-bottom: 20px; text-align: center; }}
        .details {{ background: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px; padding: 15px; margin: 15px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="error">❌ Authorization Failed</div>
        <p>There was an error connecting your Google Ads account.</p>

        <div class="details">
            <strong>Error:</strong> {error}<br>
            <strong>Details:</strong> {error_description}
        </div>

        <p>Please return to the command line and try again, or contact support if the issue persists.</p>
    </div>
</body>
</html>"""

        self._send_html_response(400, html)

    def _send_404(self):
        """Send 404 response."""
        self._send_html_response(
            404, "<h1>404 Not Found</h1><p>This is an OAuth callback server.</p>"
        )

    def _send_400(self, message: str):
        """Send 400 response."""
        self._send_html_response(400, f"<h1>400 Bad Request</h1><p>{message}</p>")

    def _send_500(self, message: str):
        """Send 500 response."""
        self._send_html_response(500, f"<h1>500 Internal Server Error</h1><p>{message}</p>")

    def _send_html_response(self, status_code: int, html: str):
        """Send HTML response with proper headers."""
        self.send_response(status_code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(html.encode("utf-8"))))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))

    def log_message(self, format, *args):
        """Suppress default HTTP logging."""
        pass


class WorkingOAuthServer:
    """OAuth callback server that actually works."""

    def __init__(self, port: int = 8080, host: str = "localhost"):
        self.port = port
        self.host = host
        self.server = None
        self.server_thread = None
        self.callback_data = {}
        self.callback_event = threading.Event()

    def find_available_port(self) -> int:
        """Find an available port."""
        for port in range(self.port, self.port + 20):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind((self.host, port))
                sock.close()
                return port
            except OSError:
                continue
        raise RuntimeError(f"No available ports found starting from {self.port}")

    def start_server(self) -> tuple[int, str]:
        """Start the OAuth callback server."""
        actual_port = self.find_available_port()

        # Set up handler
        WorkingOAuthHandler.set_data(self.callback_data, self.callback_event)

        # Create and start server
        self.server = HTTPServer((self.host, actual_port), WorkingOAuthHandler)

        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.daemon = True
        self.server_thread.start()

        redirect_uri = f"http://{self.host}:{actual_port}/callback"
        return actual_port, redirect_uri

    def wait_for_callback(self, timeout: int = 300) -> dict:
        """Wait for OAuth callback."""
        if self.callback_event.wait(timeout):
            return self.callback_data.copy()

        return {
            "success": False,
            "error": "timeout",
            "error_description": f"No OAuth callback received within {timeout} seconds",
        }

    def stop_server(self):
        """Stop the server."""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.server_thread and self.server_thread.is_alive():
            self.server_thread.join(timeout=2)
