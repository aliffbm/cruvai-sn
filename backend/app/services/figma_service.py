"""Figma Service — extract design structure and generate stories from Figma files.

Fetches Figma file data via the REST API, parses the component hierarchy,
and uses the LLM Gateway to generate an epic + stories from the design.
"""

import asyncio
import hashlib
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.services.connector_service import connector_service

logger = logging.getLogger(__name__)

# Regex to extract file key from Figma URLs
FIGMA_URL_PATTERN = re.compile(
    r"https?://[\w.-]*figma\.com/(?:design|file|board|slides)/([0-9a-zA-Z]{22,128})"
)

# In-process TTL cache for Figma file responses. Figma rate-limits per-file
# aggressively; caching for 5 minutes lets repeat imports + previews reuse.
# Key: (file_key, depth)  → (expires_at_epoch, parsed_json_dict)
_FIGMA_CACHE: dict[tuple[str, int], tuple[float, dict]] = {}
_FIGMA_CACHE_TTL_SECONDS = 300.0


async def _fetch_figma_images(
    file_key: str, node_ids: list[str], token: str,
    *, format: str = "png", scale: int = 2, max_retries: int = 3,
) -> dict[str, str]:
    """Call Figma `/v1/images` to render frames as PNG URLs.

    Returns a `{node_id: rendered_url}` map. Respects 429 Retry-After with
    bounded backoff. Uses the same strategy as the main file fetch.
    """

    if not node_ids:
        return {}

    headers = {"X-Figma-Token": token}
    url = f"https://api.figma.com/v1/images/{file_key}"
    params = {
        "ids": ",".join(node_ids),
        "format": format,
        "scale": str(scale),
    }

    attempt = 0
    while True:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.get(url, headers=headers, params=params)
        if response.status_code == 403:
            raise ValueError("Figma access denied for image export")
        if response.status_code == 404:
            raise ValueError(f"Figma file not found: {file_key}")
        if response.status_code == 429:
            if attempt >= max_retries:
                raise ValueError("Figma image export rate-limited. Try again later.")
            retry_after = response.headers.get("Retry-After")
            sleep_s = min(int(retry_after), 60) if (retry_after and retry_after.isdigit()) else min(4 * (2 ** attempt), 60)
            logger.warning("Figma images 429 attempt %d, sleeping %ss", attempt + 1, sleep_s)
            attempt += 1
            await asyncio.sleep(sleep_s)
            continue
        response.raise_for_status()
        data = response.json()
        err = data.get("err")
        if err:
            raise ValueError(f"Figma images API error: {err}")
        return data.get("images", {}) or {}


async def _fetch_figma_file_with_retry(
    file_key: str, token: str, depth: int = 3, *, max_retries: int = 3
) -> dict:
    """Fetch a Figma file with cache + 429 retry/backoff.

    Respects `Retry-After` when Figma supplies it; otherwise uses exponential
    backoff (4s, 8s, 16s). Does NOT retry 403/404 — those are terminal.
    """

    cache_key = (file_key, depth)
    cached = _FIGMA_CACHE.get(cache_key)
    now = time.monotonic()
    if cached and cached[0] > now:
        logger.info("Figma cache hit for file_key=%s depth=%d", file_key, depth)
        return cached[1]

    headers = {"X-Figma-Token": token}
    url = f"https://api.figma.com/v1/files/{file_key}"
    params = {"depth": str(depth)}

    attempt = 0
    while True:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=headers, params=params)
        if response.status_code == 403:
            raise ValueError(
                "Figma access denied. Check your Personal Access Token and file permissions."
            )
        if response.status_code == 404:
            raise ValueError(f"Figma file not found: {file_key}")
        if response.status_code == 429:
            if attempt >= max_retries:
                raise ValueError(
                    "Figma rate limit exceeded for this file. Wait ~60s and try again; "
                    "Figma applies a per-file cap on rapid requests."
                )
            retry_after_hdr = response.headers.get("Retry-After")
            if retry_after_hdr and retry_after_hdr.isdigit():
                sleep_s = min(int(retry_after_hdr), 60)
            else:
                sleep_s = min(4 * (2 ** attempt), 60)
            logger.warning(
                "Figma 429 (attempt %d/%d) for %s; sleeping %ss",
                attempt + 1, max_retries, file_key, sleep_s,
            )
            attempt += 1
            await asyncio.sleep(sleep_s)
            continue
        response.raise_for_status()
        data = response.json()
        _FIGMA_CACHE[cache_key] = (now + _FIGMA_CACHE_TTL_SECONDS, data)
        return data


@dataclass
class FigmaFrame:
    name: str
    node_id: str
    children_count: int
    component_names: list[str] = field(default_factory=list)


@dataclass
class FigmaPage:
    name: str
    node_id: str
    frames: list[FigmaFrame] = field(default_factory=list)


@dataclass
class FigmaDesign:
    file_name: str
    file_key: str
    pages: list[FigmaPage] = field(default_factory=list)
    colors: list[dict] = field(default_factory=list)
    fonts: list[str] = field(default_factory=list)


class FigmaService:
    """Extracts design structure from Figma and generates portal stories."""

    async def export_node_images(
        self,
        connector_id: uuid.UUID,
        figma_url: str,
        node_ids: list[str],
        db: Any,
        *,
        scale: int = 2,
    ) -> dict[str, str]:
        """Return a `{node_id: cdn_image_url}` map for the given nodes."""

        file_key = self.parse_file_key(figma_url)
        creds = await connector_service.get_credentials(db, connector_id, masked=False)
        token = creds.get("access_token", "")
        if not token:
            raise ValueError("Figma connector has no access_token credential")
        return await _fetch_figma_images(file_key, node_ids, token, scale=scale)

    @staticmethod
    def parse_file_key(url: str) -> str:
        """Extract the Figma file key from a URL."""
        match = FIGMA_URL_PATTERN.search(url)
        if not match:
            raise ValueError(
                f"Invalid Figma URL. Expected format: figma.com/design/FILE_KEY/... "
                f"Got: {url}"
            )
        return match.group(1)

    async def extract_design(
        self,
        connector_id: uuid.UUID,
        figma_url: str,
        db: Any,
    ) -> FigmaDesign:
        """Fetch and parse a Figma file structure.

        Args:
            connector_id: UUID of the Figma connector with credentials
            figma_url: Full Figma file URL
            db: AsyncSession for credential resolution

        Returns:
            FigmaDesign with pages, frames, colors, and fonts
        """
        file_key = self.parse_file_key(figma_url)

        # Resolve credentials from connector
        creds = await connector_service.get_credentials(db, connector_id, masked=False)
        token = creds.get("access_token", "")
        if not token:
            raise ValueError("Figma connector has no access_token credential")

        # Fetch file from Figma REST API (with cache + 429 retry)
        data = await _fetch_figma_file_with_retry(file_key, token, depth=3)

        return self._parse_figma_response(data, file_key)

    def _parse_figma_response(self, data: dict, file_key: str) -> FigmaDesign:
        """Parse Figma API response into our data classes."""
        design = FigmaDesign(
            file_name=data.get("name", "Untitled"),
            file_key=file_key,
        )

        # Extract pages and their top-level frames
        document = data.get("document", {})
        for page_node in document.get("children", []):
            if page_node.get("type") != "CANVAS":
                continue

            page = FigmaPage(
                name=page_node.get("name", "Untitled Page"),
                node_id=page_node.get("id", ""),
            )

            # Parse top-level frames (sections/screens)
            for child in page_node.get("children", []):
                if child.get("type") in ("FRAME", "COMPONENT", "COMPONENT_SET", "SECTION"):
                    component_names = self._collect_component_names(child)
                    frame = FigmaFrame(
                        name=child.get("name", "Untitled Frame"),
                        node_id=child.get("id", ""),
                        children_count=len(child.get("children", [])),
                        component_names=component_names[:20],  # Cap at 20
                    )
                    page.frames.append(frame)

            design.pages.append(page)

        # Extract colors from styles
        for style_id, style_meta in data.get("styles", {}).items():
            if style_meta.get("styleType") == "FILL":
                design.colors.append({
                    "name": style_meta.get("name", ""),
                    "description": style_meta.get("description", ""),
                })

        # Extract fonts from styles
        for style_id, style_meta in data.get("styles", {}).items():
            if style_meta.get("styleType") == "TEXT":
                design.fonts.append(style_meta.get("name", ""))

        return design

    def _collect_component_names(self, node: dict, depth: int = 0) -> list[str]:
        """Recursively collect component/frame names from a node tree."""
        if depth > 3:
            return []

        names = []
        for child in node.get("children", []):
            if child.get("type") in ("FRAME", "COMPONENT", "INSTANCE", "GROUP", "SECTION"):
                name = child.get("name", "")
                if name and not name.startswith("_"):  # Skip underscore-prefixed private components
                    names.append(name)
            names.extend(self._collect_component_names(child, depth + 1))

        return names

    def generate_story_prompt(
        self, design: FigmaDesign, portal_type: str | None = None,
    ) -> str:
        """Build the LLM prompt for generating stories from a Figma design."""
        pages_desc = []
        for page in design.pages:
            frames_list = ", ".join(f.name for f in page.frames[:10])
            components_list = []
            for f in page.frames[:5]:
                components_list.extend(f.component_names[:5])
            pages_desc.append(
                f"- **{page.name}**: Frames: [{frames_list}]. "
                f"Components: [{', '.join(components_list[:15])}]"
            )

        colors_desc = ", ".join(c["name"] for c in design.colors[:10]) if design.colors else "none detected"
        fonts_desc = ", ".join(design.fonts[:5]) if design.fonts else "none detected"
        portal_context = f"\nPortal type: {portal_type}" if portal_type else ""

        return f"""Analyze this Figma design and generate an epic with user stories for building a ServiceNow Service Portal.

## Figma Design: {design.file_name}
{portal_context}

### Pages & Components
{chr(10).join(pages_desc)}

### Design Tokens
- Colors: {colors_desc}
- Fonts: {fonts_desc}

## Instructions
Generate a JSON response with:
1. An **epic** (the overall portal build)
2. Individual **stories** — one per logical page/section, plus:
   - A "Portal Foundation" story for theme, CSS variables, and portal record
   - A "Navigation" story for the header/nav widget
   - One story per page with specific widget requirements

Each story should have:
- `title`: Clear, actionable title
- `description`: What this story delivers, referencing specific Figma components
- `acceptance_criteria`: Bulleted list of testable criteria
- `priority`: 1-4 (1=critical foundation, 2=high core pages, 3=medium secondary pages, 4=low nice-to-haves)
- `figma_node_id`: The Figma node ID for the primary frame (if applicable)

Respond with ONLY valid JSON:
{{
  "epic": {{
    "title": "Build [Portal Name] Portal",
    "description": "Complete portal build from Figma design..."
  }},
  "stories": [
    {{
      "title": "...",
      "description": "...",
      "acceptance_criteria": "- [ ] ...",
      "priority": 1,
      "figma_node_id": "..."
    }}
  ]
}}"""

    def design_to_summary(self, design: FigmaDesign) -> dict:
        """Convert design to a summary dict for the API response."""
        return {
            "file_name": design.file_name,
            "file_key": design.file_key,
            "page_count": len(design.pages),
            "pages": [
                {
                    "name": p.name,
                    "frame_count": len(p.frames),
                    "frames": [f.name for f in p.frames[:10]],
                }
                for p in design.pages
            ],
            "colors": design.colors[:10],
            "fonts": design.fonts[:5],
        }


# Singleton
figma_service = FigmaService()
