"""Basic auth adapter — username/password authentication."""

import base64

from app.services.auth.base import AuthAdapter, AuthResult


class BasicAuthAdapter(AuthAdapter):
    """Handles HTTP Basic Authentication (username:password base64 encoded).

    Used for ServiceNow instances and other systems using basic auth.
    """

    def authenticate(
        self,
        credentials: dict,
        method: str,
        url: str,
        headers: dict,
    ) -> AuthResult:
        username = credentials.get("username", "")
        password = credentials.get("password", "")

        if not username or not password:
            return AuthResult(error="Both username and password are required")

        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        return AuthResult(headers={"Authorization": f"Basic {token}"})

    def validate_credentials(self, credentials: dict) -> list[str]:
        errors = []
        if not credentials.get("username"):
            errors.append("username is required")
        if not credentials.get("password"):
            errors.append("password is required")
        return errors

    @property
    def adapter_type(self) -> str:
        return "basic_auth"
