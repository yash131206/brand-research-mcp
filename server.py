import os
import asyncio
from typing import Any
from urllib.parse import urlencode

from mcp.server import MCPServer
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

mcp = MCPServer("Brand Research MCP")

META_AD_LIBRARY = "https://www.facebook.com/ads/library/"


class BearerAuthMiddleware:
    """Minimal bearer-token gate for the remote MCP endpoint."""

    def __init__(self, app, token: str):
        self.app = app
        self.token = token.encode("utf-8")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # Render health check; deliberately exposes no private data.
        if scope.get("path") == "/health" and scope.get("method") == "GET":
            body = b"ok"
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (b"content-type", b"text/plain"),
                    (b"content-length", str(len(body)).encode()),
                ],
            })
            await send({"type": "http.response.body", "body": body})
            return

        headers = dict(scope.get("headers", []))
        auth = headers.get(b"authorization", b"")
        expected = b"Bearer " + self.token

        if auth != expected:
            body = b'{"error":"Unauthorized"}'
            await send({
                "type": "http.response.start",
                "status": 401,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                ],
            })
            await send({"type": "http.response.body", "body": body})
            return

        await self.app(scope, receive, send)


async def _read_ads_library(query: str, country: str = "IN", limit: int = 12) -> dict[str, Any]:
    """Read the public, rendered Meta Ad Library page. No login or private endpoints."""
    params = {
        "active_status": "active",
        "ad_type": "ALL",
        "country": country,
        "q": query,
        "search_type": "keyword_unordered",
    }
    url = META_AD_LIBRARY + "?" + urlencode(params)
    result: dict[str, Any] = {
        "query": query,
        "country": country,
        "url": url,
        "status": "unknown",
        "page_title": "",
        "visible_text": "",
        "ad_library_links": [],
        "notes": [
            "Public-page extraction only. Meta may limit, block, or change the page.",
            "An active ad is not evidence of profitability or performance.",
            "This tool does not expose spend, ROAS, impressions, or conversions unless Meta publicly displays them."
        ],
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = await browser.new_page(
            viewport={"width": 1440, "height": 1100},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            try:
                await page.wait_for_timeout(6500)
                await page.locator("body").wait_for(state="visible", timeout=10000)
            except PlaywrightTimeoutError:
                pass

            result["page_title"] = await page.title()
            body_text = await page.locator("body").inner_text(timeout=15000)
            result["visible_text"] = body_text[:24000]

            links = await page.locator('a[href*="ads/library"]').evaluate_all(
                """els => els.map(a => ({
                    text: (a.innerText || a.getAttribute('aria-label') || '').trim(),
                    href: a.href
                })).filter(x => x.href).slice(0, 40)"""
            )
            result["ad_library_links"] = links
            low = body_text.lower()
            if "no ads" in low or "no results" in low:
                result["status"] = "no_results_message_visible"
            elif "ad library" in low or "sponsored" in low or "started running" in low:
                result["status"] = "page_loaded_results_or_library"
            elif "temporarily blocked" in low or "try again later" in low:
                result["status"] = "rate_limited_or_blocked"
            else:
                result["status"] = "page_loaded_unclassified"
        except PlaywrightTimeoutError as exc:
            result["status"] = "navigation_timeout"
            result["error"] = str(exc)
        except Exception as exc:
            result["status"] = "extraction_error"
            result["error"] = f"{type(exc).__name__}: {exc}"
        finally:
            await browser.close()

    return result


@mcp.tool()
async def search_meta_ads_library(
    brand_name: str,
    country: str = "IN",
) -> dict:
    """Search Meta's public Ad Library page for a brand. Returns rendered public page text and ad-library links; verify exact advertiser matches manually."""
    brand_name = brand_name.strip()
    if not brand_name:
        return {"error": "brand_name is required"}
    if len(brand_name) > 120:
        return {"error": "brand_name is too long"}
    if country not in {"IN", "US", "GB", "CA", "AU"}:
        return {"error": "Supported country codes: IN, US, GB, CA, AU"}
    return await _read_ads_library(brand_name, country)


@mcp.tool()
async def research_multiple_brands(
    brand_names: list[str],
    country: str = "IN",
) -> list[dict]:
    """Research up to five brands sequentially in the public Meta Ad Library. Use small batches to reduce rate-limit risk."""
    cleaned = [x.strip() for x in brand_names if x and x.strip()]
    if not cleaned:
        return [{"error": "Provide at least one brand name"}]
    if len(cleaned) > 5:
        return [{"error": "Maximum five brands per call. Run another batch after reviewing results."}]
    results = []
    for name in cleaned:
        results.append(await _read_ads_library(name, country))
        await asyncio.sleep(3)
    return results


@mcp.tool()
def build_meta_ads_library_url(
    brand_name: str,
    country: str = "IN",
    active_status: str = "active",
) -> str:
    """Build a direct public Meta Ad Library search URL for manual verification."""
    if not brand_name.strip():
        raise ValueError("brand_name is required")
    if country not in {"IN", "US", "GB", "CA", "AU"}:
        raise ValueError("Unsupported country code")
    if active_status not in {"active", "inactive", "all"}:
        raise ValueError("active_status must be active, inactive, or all")
    return META_AD_LIBRARY + "?" + urlencode({
        "active_status": active_status,
        "ad_type": "ALL",
        "country": country,
        "q": brand_name.strip(),
        "search_type": "keyword_unordered",
    })


if __name__ == "__main__":
    token = os.environ.get("MCP_API_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Set MCP_API_TOKEN before starting the remote server.")
    app = BearerAuthMiddleware(mcp.streamable_http_app(host="0.0.0.0"), token)
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
