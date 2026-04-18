"""Base auth adapter — interface for all authentication handlers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AuthResult:
    """Result of an authentication operation."""

    headers: dict = field(default_factory=dict)
    query_params: dict = field(default_factory=dict)
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None


class AuthAdapter(ABC):
    """Base class for connector authentication adapters.

    Each adapter type handles a specific auth method (Bearer, Basic Auth, etc.)
    and knows how to transform credentials into HTTP headers/params.
    """

    @abstractmethod
    def authenticate(
        self,
        credentials: dict,
        method: str,
        url: str,
        headers: dict,
    ) -> AuthResult:
        """Apply authentication to an outgoing request.

        Args:
            credentials: Decrypted credential dict from connector
            method: HTTP method (GET, POST, etc.)
            url: Full request URL
            headers: Existing headers to merge with

        Returns:
            AuthResult with headers/params to apply, or error
        """
        ...

    @abstractmethod
    def validate_credentials(self, credentials: dict) -> list[str]:
        """Check that required credential fields are present.

        Returns:
            List of error messages (empty = valid)
        """
        ...

    @property
    @abstractmethod
    def adapter_type(self) -> str:
        """Unique identifier for this adapter type."""
        ...
