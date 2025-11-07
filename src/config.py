import os

VERSION: str = "0.2.4"
"""Current version of the project."""

SESSION_EXPIRY_DAYS: int = int(os.getenv("SESSION_EXPIRY_DAYS", "7"))
"""Number of days before a user session expires."""

PAC_DEFAULT_RESPONSE: str = os.getenv(
    "PAC_DEFAULT_RESPONSE",
    """
function FindProxyForURL(url, host) {
    return "DIRECT";
}
""",
)

PAC_BUILTIN_PROXY_RESPONSE: str = os.getenv(
    "PAC_BUILTIN_PROXY_RESPONSE",
    """
function FindProxyForURL(url, host) {
    // Use built-in proxy
    return "PROXY %s:%s";
}
""",
)

PAC_UNAUTHORIZED_RESPONSE: str = os.getenv(
    "PAC_UNAUTHORIZED_RESPONSE",
    """
function FindProxyForURL(url, host) {
    alert("Unauthorized device. Proxy access denied.");
    return "DIRECT";
}
""",
)

PAC_MEDIA_TYPE: str = os.getenv("PAC_MEDIA_TYPE", "application/x-ns-proxy-autoconfig")
"""Media type for PAC file responses."""
