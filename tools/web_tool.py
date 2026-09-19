import base64
import html as html_mod
import logging
import os
import re
from typing import List, Dict, Any

import httpx

logger = logging.getLogger("WebTool")

_BING_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
_BING_HEADERS = {
    "User-Agent": _BING_UA,
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml",
}


def _decode_bing_ck(href: str) -> str:
    """Bing result hrefs are /ck/a? redirects carrying the real URL as a
    base64url parameter (u=a1<base64url>). Decode when possible; otherwise
    return the href as-is (it still redirects correctly)."""
    m = re.search(r"[?&]u=a1([A-Za-z0-9_-]+)", href)
    if not m:
        return href
    try:
        pad = "=" * (-len(m.group(1)) % 4)
        raw = base64.urlsafe_b64decode(m.group(1) + pad)
        return raw.decode("utf-8", "replace")
    except Exception:
        return href


class WebTool:
    """Web search with automatic provider fallback:

      1. Brave API  — used when BRAVE_API_KEY is configured (structured JSON).
      2. Bing HTML  — keyless fallback (search-engine-tool style scraping,
         no browser/driver needed) when Brave is absent or fails.
    """

    def __init__(self):
        self.api_key = os.environ.get("BRAVE_API_KEY", "")
        self.client = httpx.AsyncClient(timeout=20.0)

    async def search(self, query: str, count: int = 5) -> List[Dict[str, str]]:
        if self.api_key:
            results = await self._search_brave(query, count)
            if results:
                return results
        return await self._search_bing_keyless(query, count)

    def search_sync(self, query: str, count: int = 5) -> List[Dict[str, str]]:
        """Synchronous variant for the headless task runtime (engine workers
        are thread-based, not async). Same provider order as search()."""
        if self.api_key:
            results = self._search_brave_sync(query, count)
            if results:
                return results
        return self._search_bing_sync(query, count)

    def _search_brave_sync(self, query: str, count: int) -> List[Dict[str, str]]:
        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    headers={"Accept": "application/json",
                             "X-Subscription-Token": self.api_key},
                    params={"q": query, "count": count},
                )
            if resp.status_code != 200:
                return []
            web_results = resp.json().get("web", {}).get("results", [])
            return [{"title": r.get("title", ""), "url": r.get("url", ""),
                     "snippet": r.get("description", "")} for r in web_results[:count]]
        except Exception as e:
            logger.warning(f"Brave sync failed: {e}")
            return []

    def _search_bing_sync(self, query: str, count: int) -> List[Dict[str, str]]:
        try:
            with httpx.Client(timeout=20.0, headers=_BING_HEADERS) as client:
                resp = client.get("https://www.bing.com/search", params={"q": query, "count": count})
            if resp.status_code != 200:
                return []
            return self._parse_bing(resp.text, count)
        except Exception as e:
            logger.warning(f"Keyless Bing sync failed: {e}")
            return []

    # ---- provider 1: Brave API (keyed) ----
    async def _search_brave(self, query: str, count: int) -> List[Dict[str, str]]:
        try:
            resp = await self.client.get(
                "https://api.search.brave.com/res/v1/web/search",
                headers={"Accept": "application/json",
                         "X-Subscription-Token": self.api_key},
                params={"q": query, "count": count},
            )
            if resp.status_code != 200:
                logger.warning(f"Brave search HTTP {resp.status_code}; falling back")
                return []
            data = resp.json()
            web_results = data.get("web", {}).get("results", [])
            return [
                {
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("description", ""),
                }
                for r in web_results[:count]
            ]
        except Exception as e:
            logger.warning(f"Brave Search failed: {e}; falling back")
            return []

    # ---- provider 2: Bing HTML scraping (keyless) ----
    async def _search_bing_keyless(self, query: str, count: int) -> List[Dict[str, str]]:
        try:
            resp = await self.client.get(
                "https://www.bing.com/search",
                headers=_BING_HEADERS,
                params={"q": query, "count": count},
            )
            if resp.status_code != 200:
                return []
            return self._parse_bing(resp.text, count)
        except Exception as e:
            logger.warning(f"Keyless Bing search failed: {e}")
            return []

    @staticmethod
    def _parse_bing(page: str, count: int) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        items = re.findall(r'<li class="b_algo".*?</li>', page, re.S)
        for it in items:
            m = re.search(r'<h2[^>]*><a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', it, re.S)
            if not m:
                continue
            url = html_mod.unescape(m.group(1))
            url = _decode_bing_ck(url)
            title = re.sub(r"<[^>]+>", "", m.group(2))
            m2 = re.search(r"<p[^>]*>(.*?)</p>", it, re.S)
            snippet = re.sub(r"<[^>]+>", "", m2.group(1)) if m2 else ""
            out.append({
                "title": html_mod.unescape(title).strip(),
                "url": url,
                "snippet": html_mod.unescape(snippet).strip(),
            })
            if len(out) >= count:
                break
        return out

    def format_search_results(self, results: List[Dict[str, str]], query: str) -> str:
        if not results:
            if not self.api_key:
                return (f"[No live web results for '{query}' — keyless Bing "
                        f"fallback returned nothing; reasoning from general knowledge.]")
            return f"[No web search results returned for '{query}']"

        source = "Brave API" if self.api_key else "keyless Bing (search-engine-tool style)"
        lines = [f"[LIVE WEB SEARCH RESULTS ({source}) FOR: {query}]"]
        for idx, r in enumerate(results, 1):
            lines.append(f"{idx}. {r['title']}\n   URL: {r['url']}\n   Summary: {r['snippet']}")
        return "\n".join(lines)


web_tool = WebTool()
