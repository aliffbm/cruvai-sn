"""Connector service — credential management, verification, and action execution."""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.connector import Connector, ConnectorAction
from app.services.auth import get_auth_adapter
from app.utils.encryption import encrypt_value, decrypt_value

logger = logging.getLogger(__name__)


class ConnectorService:
    """Manages connector credentials, verification, and action execution."""

    # --- Credential Management ---

    async def save_credentials(
        self, db: AsyncSession, connector_id: uuid.UUID, credentials: dict
    ) -> Connector:
        """Save (merge) encrypted credentials on a connector.

        Merges with existing credentials — partial updates supported.
        Empty-value keys are removed.
        """
        result = await db.execute(
            select(Connector).where(Connector.id == connector_id)
        )
        connector = result.scalar_one_or_none()
        if not connector:
            raise ValueError(f"Connector {connector_id} not found")

        # Merge with existing creds
        existing = {}
        if connector.credentials_encrypted:
            try:
                existing = json.loads(decrypt_value(connector.credentials_encrypted))
            except Exception:
                existing = {}

        merged = {**existing, **credentials}
        # Remove keys with empty values
        merged = {k: v for k, v in merged.items() if v}

        connector.credentials_encrypted = encrypt_value(json.dumps(merged))
        connector.status = "connected" if merged else "disconnected"
        await db.flush()
        await db.refresh(connector)
        return connector

    async def get_credentials(
        self, db: AsyncSession, connector_id: uuid.UUID, masked: bool = True
    ) -> dict:
        """Get connector credentials.

        Args:
            masked: If True, returns masked values (first 4 + last 4 chars).
                    If False, returns raw decrypted values (internal use only).
        """
        result = await db.execute(
            select(Connector).where(Connector.id == connector_id)
        )
        connector = result.scalar_one_or_none()
        if not connector or not connector.credentials_encrypted:
            return {}

        creds = json.loads(decrypt_value(connector.credentials_encrypted))

        if masked:
            return {
                k: self._mask_value(v, key=k) if isinstance(v, str) else v
                for k, v in creds.items()
            }
        return creds

    async def clear_credentials(
        self, db: AsyncSession, connector_id: uuid.UUID
    ) -> Connector:
        """Clear all credentials from a connector."""
        result = await db.execute(
            select(Connector).where(Connector.id == connector_id)
        )
        connector = result.scalar_one_or_none()
        if not connector:
            raise ValueError(f"Connector {connector_id} not found")

        connector.credentials_encrypted = None
        connector.status = "disconnected"
        await db.flush()
        return connector

    # --- Verification ---

    async def verify_connector(
        self, db: AsyncSession, connector_id: uuid.UUID
    ) -> dict:
        """Test a connector's credentials by making a live API call."""
        result = await db.execute(
            select(Connector).where(Connector.id == connector_id)
        )
        connector = result.scalar_one_or_none()
        if not connector:
            raise ValueError(f"Connector {connector_id} not found")

        if not connector.credentials_encrypted:
            connector.status = "error"
            connector.status_message = "No credentials configured"
            await db.flush()
            return {"status": "error", "message": "No credentials configured"}

        creds = json.loads(decrypt_value(connector.credentials_encrypted))
        adapter = get_auth_adapter(connector.connector_type, connector.config)

        # Validate credential fields
        errors = adapter.validate_credentials(creds)
        if errors:
            connector.status = "error"
            connector.status_message = "; ".join(errors)
            await db.flush()
            return {"status": "error", "message": connector.status_message}

        # Platform-specific live checks
        try:
            check_result = await self._live_check(connector.platform, creds, adapter)
            connector.status = "connected"
            connector.status_message = check_result.get("message", "Connection verified")
            connector.last_verified_at = datetime.now(timezone.utc)
            await db.flush()
            return {"status": "connected", **check_result}
        except Exception as e:
            connector.status = "error"
            connector.status_message = str(e)
            await db.flush()
            return {"status": "error", "message": str(e)}

    async def _live_check(self, platform: str, creds: dict, adapter: Any) -> dict:
        """Platform-specific credential verification."""
        import httpx

        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            if platform == "anthropic":
                auth_result = adapter.authenticate(creds, "GET", "https://api.anthropic.com/v1/models", {})
                headers = {"anthropic-version": "2023-06-01", **auth_result.headers}
                # Anthropic uses x-api-key, not Bearer
                if creds.get("api_key"):
                    headers["x-api-key"] = creds["api_key"]
                    headers.pop("Authorization", None)
                r = await client.get("https://api.anthropic.com/v1/models", headers=headers)
                if r.status_code == 200:
                    return {"message": "Anthropic API key verified"}
                raise ValueError(f"Anthropic API returned {r.status_code}")

            elif platform == "openai":
                auth_result = adapter.authenticate(creds, "GET", "https://api.openai.com/v1/models", {})
                r = await client.get("https://api.openai.com/v1/models", headers=auth_result.headers)
                if r.status_code == 200:
                    return {"message": "OpenAI API key verified"}
                raise ValueError(f"OpenAI API returned {r.status_code}")

            elif platform == "figma":
                token = creds.get("access_token", "")
                if not token:
                    raise ValueError("access_token is required")
                r = await client.get(
                    "https://api.figma.com/v1/me",
                    headers={"X-Figma-Token": token},
                )
                if r.status_code == 200:
                    user_data = r.json()
                    return {"message": f"Figma connected as {user_data.get('email', user_data.get('handle', 'unknown'))}"}
                elif r.status_code == 403:
                    raise ValueError("Figma token is invalid or expired")
                raise ValueError(f"Figma API returned {r.status_code}")

            elif platform == "servicenow":
                instance_url = creds.get("instance_url", "").rstrip("/")
                if not instance_url:
                    raise ValueError("instance_url is required")
                auth_result = adapter.authenticate(creds, "GET", f"{instance_url}/api/now/table/sys_properties", {})
                headers = {"Accept": "application/json", **auth_result.headers}
                r = await client.get(
                    f"{instance_url}/api/now/table/sys_properties",
                    headers=headers,
                    params={"sysparm_query": "name=glide.buildtag.last", "sysparm_limit": "1"},
                )
                if r.status_code == 200:
                    data = r.json()
                    records = data.get("result", [])
                    build = records[0].get("value", "unknown") if records else "unknown"
                    return {"message": f"ServiceNow connected (build: {build})"}
                raise ValueError(f"ServiceNow API returned {r.status_code}")

            else:
                # Generic check: just validate credentials are present
                return {"message": f"Credentials saved for {platform} (no live check available)"}

    # --- Action Execution ---

    async def execute_action(
        self, db: AsyncSession, action_id: uuid.UUID, params: dict
    ) -> dict:
        """Execute a connector action with the given parameters."""
        result = await db.execute(
            select(ConnectorAction)
            .options(selectinload(ConnectorAction.connector))
            .where(ConnectorAction.id == action_id)
        )
        action = result.scalar_one_or_none()
        if not action or not action.connector:
            raise ValueError(f"Action {action_id} not found or has no connector")

        connector = action.connector
        if not connector.credentials_encrypted:
            raise ValueError("Connector has no credentials configured")

        creds = json.loads(decrypt_value(connector.credentials_encrypted))
        adapter = get_auth_adapter(connector.connector_type, connector.config)

        # Build request
        base_url = action.base_url or connector.base_url or ""
        url = f"{base_url.rstrip('/')}{action.endpoint_path}"

        # Interpolate credential placeholders in headers
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if action.headers_template:
            for key, value in action.headers_template.items():
                if isinstance(value, str):
                    for cred_key, cred_val in creds.items():
                        value = value.replace(f"{{{cred_key}}}", str(cred_val))
                headers[key] = value

        # Apply auth adapter
        auth_result = adapter.authenticate(creds, action.method, url, headers)
        if not auth_result.success:
            raise ValueError(f"Authentication failed: {auth_result.error}")
        headers.update(auth_result.headers)

        # Build body from template + params
        body = None
        if action.method in ("POST", "PUT", "PATCH"):
            body = {**(action.request_body_template or {}), **params}

        import httpx
        async with httpx.AsyncClient(timeout=action.timeout_seconds) as client:
            response = await client.request(
                method=action.method,
                url=url,
                headers=headers,
                json=body if body else None,
                params=params if action.method == "GET" else None,
            )

        return {
            "status_code": response.status_code,
            "body": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
            "headers": dict(response.headers),
        }

    # --- Helpers ---

    # Credential keys that must be fully masked (never reveal any characters).
    # Matches by case-insensitive substring against the credential key name.
    _FULL_MASK_KEY_SUBSTRINGS = (
        "password",
        "secret",
        "private_key",
        "client_secret",
    )

    @classmethod
    def _mask_value(cls, value: str, *, key: str | None = None) -> str:
        """Mask a credential value.

        - For password/secret/private_key/client_secret fields: fully mask
          (no length hint, no characters revealed).
        - For other credentials (e.g. username, instance_url, tokens where a
          partial hint helps the user verify which one is stored): show the
          first 4 and last 4 characters.
        """
        if key is not None:
            key_lc = key.lower()
            if any(sub in key_lc for sub in cls._FULL_MASK_KEY_SUBSTRINGS):
                # Constant-length placeholder so the UI can't infer length.
                return "••••••••"
        if len(value) <= 8:
            return "*" * len(value)
        return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"


# Singleton
connector_service = ConnectorService()
