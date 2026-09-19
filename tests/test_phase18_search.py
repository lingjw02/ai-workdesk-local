"""Phase 18 — keyless web search fallback (search-engine-tool integration).

Brave API remains provider #1 when BRAVE_API_KEY is set; when absent or
failing, WebTool now falls back to keyless Bing HTML scraping (the
search-engine-tool approach, without browser/driver dependencies).

These tests are offline: they feed fixed HTML into the parser and stub the
HTTP client to verify the fallback wiring.
"""
import asyncio
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, ".")
from tools.web_tool import WebTool, _decode_bing_ck

SAMPLE_BING = """
<ol id="b_results">
<li class="b_algo">
  <h2><a href="https://www.bing.com/ck/a?!&amp;&amp;p=abc&amp;u=a1aHR0cHM6Ly9leGFtcGxlLmNvbS9wYWdl">Example Result</a></h2>
  <p>This is the snippet text for the first result.</p>
  <cite>example.com</cite>
</li>
<li class="b_algo">
  <h2><a href="https://example.org/plain">Second Result</a></h2>
  <p>Second snippet.</p>
</li>
<li class="b_algo">
  <h2><a href="https://www.bing.com/ck/a?u=a1aHR0cHM6Ly90aGlyZC5uZXQv">Third</a></h2>
  <p></p>
</li>
</ol>
"""


class TestBingKeylessSearch(unittest.TestCase):
    def test_parse_bing_extracts_three(self):
        out = WebTool._parse_bing(SAMPLE_BING, count=5)
        self.assertEqual(len(out), 3)
        self.assertEqual(out[0]["title"], "Example Result")
        self.assertEqual(out[0]["snippet"], "This is the snippet text for the first result.")
        self.assertEqual(out[1]["url"], "https://example.org/plain")

    def test_parse_bing_respects_count(self):
        out = WebTool._parse_bing(SAMPLE_BING, count=2)
        self.assertEqual(len(out), 2)

    def test_ck_url_decoding(self):
        # base64url of "https://example.com/page" with leading a1 marker
        self.assertEqual(
            _decode_bing_ck("https://www.bing.com/ck/a?u=a1aHR0cHM6Ly9leGFtcGxlLmNvbS9wYWdl"),
            "https://example.com/page")
        # non-ck href passes through untouched
        self.assertEqual(_decode_bing_ck("https://example.org/plain"),
                         "https://example.org/plain")

    def test_fallback_to_bing_when_brave_empty(self):
        wt = WebTool()
        wt.api_key = "fake-key"
        # Brave returns empty -> fall back to Bing
        wt._search_brave = AsyncMock(return_value=[])
        wt._search_bing_keyless = AsyncMock(return_value=[
            {"title": "K", "url": "https://k", "snippet": "s"}])
        out = asyncio.run(wt.search("q", count=3))
        self.assertEqual(out, [{"title": "K", "url": "https://k", "snippet": "s"}])
        wt._search_bing_keyless.assert_awaited_once()

    def test_bing_first_when_no_key(self):
        wt = WebTool()
        wt.api_key = ""
        wt._search_bing_keyless = AsyncMock(return_value=[
            {"title": "B", "url": "https://b", "snippet": "s"}])
        out = asyncio.run(wt.search("q", count=3))
        self.assertEqual(out[0]["title"], "B")

    def test_format_mentions_source(self):
        wt = WebTool()
        wt.api_key = ""
        text = wt.format_search_results(
            [{"title": "T", "url": "https://t", "snippet": "S"}], "hello")
        self.assertIn("keyless Bing", text)
        wt.api_key = "k"
        text2 = wt.format_search_results(
            [{"title": "T", "url": "https://t", "snippet": "S"}], "hello")
        self.assertIn("Brave", text2)


if __name__ == "__main__":
    unittest.main()
