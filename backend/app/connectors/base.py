import asyncio
import logging
import uuid
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.instance import InstanceCredential, ServiceNowInstance
from app.utils.encryption import decrypt_value

logger = logging.getLogger(__name__)


class ServiceNowAPIError(Exception):
    def __init__(self, status_code: int, message: str, detail: dict | None = None):
        self.status_code = status_code
        self.message = message
        self.detail = detail
        super().__init__(f"ServiceNow API error {status_code}: {message}")


class BaseServiceNowConnector:
    def __init__(
        self,
        instance_url: str,
        username: str | None = None,
        password: str | None = None,
        access_token: str | None = None,
        rate_limit_rpm: int = 100,
    ):
        self.instance_url = instance_url.rstrip("/")
        self.username = username
        self.password = password
        self.access_token = access_token
        self.rate_limit_rpm = rate_limit_rpm
        self._semaphore = asyncio.Semaphore(10)  # Max concurrent requests
        self._client: httpx.AsyncClient | None = None

    @classmethod
    async def from_instance(
        cls, instance: ServiceNowInstance, db: AsyncSession
    ) -> "BaseServiceNowConnector":
        result = await db.execute(
            select(InstanceCredential).where(
                InstanceCredential.instance_id == instance.id,
                InstanceCredential.is_active.is_(True),
            )
        )
        cred = result.scalar_one_or_none()
        if not cred:
            raise ValueError(f"No active credentials for instance {instance.name}")

        username = decrypt_value(cred.username_encrypted) if cred.username_encrypted else None
        password = decrypt_value(cred.password_encrypted) if cred.password_encrypted else None
        access_token = decrypt_value(cred.access_token_encrypted) if cred.access_token_encrypted else None

        return cls(
            instance_url=instance.instance_url,
            username=username,
            password=password,
            access_token=access_token,
        )

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            auth = None
            headers = {"Accept": "application/json", "Content-Type": "application/json"}
            if self.access_token:
                headers["Authorization"] = f"Bearer {self.access_token}"
            elif self.username and self.password:
                auth = httpx.BasicAuth(self.username, self.password)
            self._client = httpx.AsyncClient(
                base_url=self.instance_url,
                auth=auth,
                headers=headers,
                timeout=httpx.Timeout(30.0, connect=10.0),
            )
        return self._client

    async def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        json_data: dict | None = None,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        client = await self._get_client()
        request_id = str(uuid.uuid4())[:8]

        for attempt in range(max_retries):
            async with self._semaphore:
                try:
                    response = await client.request(
                        method,
                        path,
                        params=params,
                        json=json_data,
                        headers={"X-Cruvai-Request-Id": request_id},
                    )

                    if response.status_code == 429:
                        wait = min(2 ** attempt * 2, 30)
                        logger.warning(f"Rate limited, waiting {wait}s (attempt {attempt + 1})")
                        await asyncio.sleep(wait)
                        continue

                    if response.status_code >= 500:
                        if attempt < max_retries - 1:
                            wait = 2 ** attempt
                            logger.warning(f"Server error {response.status_code}, retrying in {wait}s")
                            await asyncio.sleep(wait)
                            continue

                    if response.status_code >= 400:
                        detail = None
                        try:
                            detail = response.json()
                        except Exception:
                            pass
                        raise ServiceNowAPIError(response.status_code, response.text[:500], detail)

                    return response.json()

                except httpx.RequestError as e:
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    raise ServiceNowAPIError(0, f"Connection error: {e}")

        raise ServiceNowAPIError(0, "Max retries exceeded")

    async def test_connection(self) -> dict:
        result = await self._request("GET", "/api/now/table/sys_properties", params={
            "sysparm_query": "name=glide.buildtag",
            "sysparm_fields": "name,value",
            "sysparm_limit": "1",
        })
        records = result.get("result", [])
        build_tag = records[0]["value"] if records else "unknown"
        return {"build_tag": build_tag, "status": "connected"}

    async def get_record(
        self, table: str, sys_id: str, fields: list[str] | None = None
    ) -> dict:
        params = {}
        if fields:
            params["sysparm_fields"] = ",".join(fields)
        params["sysparm_display_value"] = "true"
        result = await self._request("GET", f"/api/now/table/{table}/{sys_id}", params=params)
        return result.get("result", {})

    async def query_records(
        self,
        table: str,
        query: str = "",
        fields: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str | None = None,
    ) -> list[dict]:
        params: dict[str, Any] = {"sysparm_limit": str(limit), "sysparm_offset": str(offset)}
        if query:
            params["sysparm_query"] = query
        if fields:
            params["sysparm_fields"] = ",".join(fields)
        if order_by:
            params["sysparm_query"] = f"{params.get('sysparm_query', '')}^ORDERBY{order_by}"
        params["sysparm_display_value"] = "true"
        result = await self._request("GET", f"/api/now/table/{table}", params=params)
        return result.get("result", [])

    async def create_record(self, table: str, data: dict) -> dict:
        result = await self._request("POST", f"/api/now/table/{table}", json_data=data)
        return result.get("result", {})

    async def update_record(self, table: str, sys_id: str, data: dict) -> dict:
        result = await self._request("PATCH", f"/api/now/table/{table}/{sys_id}", json_data=data)
        return result.get("result", {})

    async def delete_record(self, table: str, sys_id: str) -> bool:
        await self._request("DELETE", f"/api/now/table/{table}/{sys_id}")
        return True

    async def get_table_schema(self, table: str) -> list[dict]:
        records = await self.query_records(
            "sys_dictionary",
            query=f"name={table}^internal_type!=collection",
            fields=["element", "column_label", "internal_type", "mandatory", "max_length", "reference"],
            limit=500,
        )
        return records

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
