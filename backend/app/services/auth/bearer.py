"""Bearer token / API key auth adapter."""

from app.services.auth.base import AuthAdapter, AuthResult


class BearerTokenAdapter(AuthAdapter):
    """Handles Bearer token, API key, and OAuth token auth.

    Tries multiple credential field names in priority order:
    bearer_token > access_token > api_token > api_key
    """

    # Fields to check for the token, in priority order
    TOKEN_FIELDS = [
        "bearer_token",
        "access_token",
        "personal_access_token",
        "api_token",
        "bot_token",
        "api_key",
    ]

    def authenticate(
        self,
        credentials: dict,
        method: str,
        url: str,
        headers: dict,
    ) -> AuthResult:
        token = None
        for field in self.TOKEN_FIELDS:
            if credentials.get(field):
                token = credentials[field]
                break

        if not token:
            return AuthResult(error="No token found in credentials")

        # Some APIs use custom header names (e.g., Anthropic uses x-api-key)
        custom_header = credentials.get("_auth_header")
        if custom_header:
            return AuthResult(headers={custom_header: token})

        return AuthResult(headers={"Authorization": f"Bearer {token}"})

    def validate_credentials(self, credentials: dict) -> list[str]:
        for field in self.TOKEN_FIELDS:
            if credentials.get(field):
                return []
        return [f"At least one of {', '.join(self.TOKEN_FIELDS)} is required"]

    @property
    def adapter_type(self) -> str:
        return "bearer_token"
