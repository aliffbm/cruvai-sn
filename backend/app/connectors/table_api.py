from typing import Any

from app.connectors.base import BaseServiceNowConnector


class TableAPIConnector(BaseServiceNowConnector):
    """Convenience wrapper for common ServiceNow Table API patterns."""

    async def create_catalog_item(
        self,
        name: str,
        category: str | None = None,
        short_description: str = "",
        description: str = "",
        scope_sys_id: str | None = None,
    ) -> dict:
        data: dict[str, Any] = {
            "name": name,
            "short_description": short_description,
            "description": description,
            "active": "true",
        }
        if category:
            data["category"] = category
        return await self.create_record("sc_cat_item", data)

    async def create_catalog_variable(
        self,
        cat_item_sys_id: str,
        name: str,
        question_text: str,
        variable_type: str = "6",  # Single line text
        mandatory: bool = False,
        order: int = 100,
    ) -> dict:
        data = {
            "cat_item": cat_item_sys_id,
            "name": name,
            "question_text": question_text,
            "type": variable_type,
            "mandatory": str(mandatory).lower(),
            "order": str(order),
        }
        return await self.create_record("item_option_new", data)

    async def create_business_rule(
        self,
        name: str,
        table: str,
        script: str,
        when: str = "after",
        insert: bool = False,
        update: bool = False,
        delete: bool = False,
        query: bool = False,
        active: bool = True,
    ) -> dict:
        data = {
            "name": name,
            "collection": table,
            "script": script,
            "when": when,
            "action_insert": str(insert).lower(),
            "action_update": str(update).lower(),
            "action_delete": str(delete).lower(),
            "action_query": str(query).lower(),
            "active": str(active).lower(),
        }
        return await self.create_record("sys_script", data)

    async def create_client_script(
        self,
        name: str,
        table: str,
        script: str,
        script_type: str = "onChange",
        active: bool = True,
    ) -> dict:
        data = {
            "name": name,
            "table": table,
            "script": script,
            "type": script_type,
            "active": str(active).lower(),
        }
        return await self.create_record("sys_script_client", data)

    async def create_ui_policy(
        self,
        name: str,
        table: str,
        conditions: str = "",
        active: bool = True,
    ) -> dict:
        data = {
            "short_description": name,
            "table": table,
            "conditions": conditions,
            "active": str(active).lower(),
        }
        return await self.create_record("sys_ui_policy", data)

    async def create_update_set(self, name: str, description: str = "") -> dict:
        data = {
            "name": name,
            "description": description,
            "state": "in progress",
        }
        return await self.create_record("sys_update_set", data)

    async def list_update_sets(self, state: str = "in progress") -> list[dict]:
        return await self.query_records(
            "sys_update_set",
            query=f"state={state}",
            fields=["name", "description", "state", "sys_id"],
            limit=50,
        )

    async def list_scopes(self) -> list[dict]:
        return await self.query_records(
            "sys_scope",
            fields=["scope", "name", "sys_id"],
            limit=100,
        )
