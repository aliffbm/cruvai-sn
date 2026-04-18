"""Auth adapter system — pluggable authentication for connectors."""

from app.services.auth.base import AuthAdapter, AuthResult
from app.services.auth.registry import get_auth_adapter, register_adapter

__all__ = ["AuthAdapter", "AuthResult", "get_auth_adapter", "register_adapter"]
