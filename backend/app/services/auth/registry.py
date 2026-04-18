"""Auth adapter registry — maps connector_type to adapter implementation."""

from typing import Optional

from app.services.auth.base import AuthAdapter, AuthResult
from app.services.auth.bearer import BearerTokenAdapter
from app.services.auth.basic import BasicAuthAdapter


class NoAuthAdapter(AuthAdapter):
    """Pass-through adapter for connectors that don't need auth."""

    def authenticate(self, credentials, method, url, headers):
        return AuthResult()

    def validate_credentials(self, credentials):
        return []

    @property
    def adapter_type(self):
        return "none"


# Registry mapping connector_type → adapter class
_ADAPTERS: dict[str, type[AuthAdapter]] = {
    "api_key": BearerTokenAdapter,
    "bearer_token": BearerTokenAdapter,
    "oauth2": BearerTokenAdapter,
    "basic_auth": BasicAuthAdapter,
    "none": NoAuthAdapter,
}


def get_auth_adapter(
    connector_type: str, config: Optional[dict] = None
) -> AuthAdapter:
    """Get the appropriate auth adapter for a connector type.

    Args:
        connector_type: The connector's auth type (api_key, bearer_token, basic_auth, etc.)
        config: Optional connector config for adapter customization

    Returns:
        Instantiated AuthAdapter
    """
    adapter_cls = _ADAPTERS.get(connector_type, NoAuthAdapter)
    return adapter_cls()


def register_adapter(connector_type: str, adapter_cls: type[AuthAdapter]) -> None:
    """Register a custom auth adapter for a connector type.

    Allows extending the system with new auth methods (e.g., AWS SigV4, GCP service accounts).
    """
    _ADAPTERS[connector_type] = adapter_cls
