"""Lightweight web search using DuckDuckGo HTML.

No API key required. Scrapes DuckDuckGo search results for academic
reference lookup. Returns title, snippet, and URL for each result.
"""

import logging
import re
from urllib.parse import quote_plus

import httpx

logger = logging.getLogger(__name__)


async def web_search(query: str, num_results: int = 5) -> list[dict]:
    """Search DuckDuckGo HTML and return structured results."""
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
    except Exception:
        logger.debug("web_search failed for query: %s", query, exc_info=True)
        return []

    html = resp.text
    results = []

    # Extract result blocks: <a class="result__a" href="...">title</a>
    # and <a class="result__snippet">snippet</a>
    blocks = re.findall(
        r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?'
        r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
        html,
        re.DOTALL,
    )

    for href, title_raw, snippet_raw in blocks[:num_results]:
        title = re.sub(r"<[^>]+>", "", title_raw).strip()
        snippet = re.sub(r"<[^>]+>", "", snippet_raw).strip()
        # DuckDuckGo wraps URLs in a redirect; extract the actual URL
        actual_url = href
        uddg = re.search(r"uddg=([^&]+)", href)
        if uddg:
            from urllib.parse import unquote
            actual_url = unquote(uddg.group(1))
        results.append({
            "title": title,
            "snippet": snippet,
            "url": actual_url,
        })

    return results


def format_web_results(results: list[dict]) -> str:
    """Format web results into a readable string for the LLM prompt."""
    if not results:
        return ""
    parts = []
    for i, r in enumerate(results, 1):
        parts.append(f"[Web Result {i}] {r['title']}\n{r['snippet']}\n{r['url']}")
    return "\n\n".join(parts)
