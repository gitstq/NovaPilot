"""Web search and URL content fetching tool for NovaPilot.

Provides basic web search capabilities and URL content retrieval
using only urllib from the Python standard library.
"""

import json
import re
import ssl
import urllib.request
import urllib.parse
import urllib.error
import html


class WebSearch:
    """Web search and content fetching tool.

    Uses DuckDuckGo's instant answer API for searches and urllib
    for fetching web page content. No API keys required.
    """

    # Trigger patterns for automatic tool activation
    trigger_patterns = [
        "search", "look up", "find on web", "google",
        "fetch url", "get webpage", "http",
    ]

    def __init__(self, timeout=15, max_content_length=50000):
        """Initialize WebSearch.

        Args:
            timeout: Request timeout in seconds.
            max_content_length: Maximum content length to fetch (bytes).
        """
        self.timeout = timeout
        self.max_content_length = max_content_length

    def search(self, query, num_results=5):
        """Perform a web search using DuckDuckGo.

        Uses DuckDuckGo's instant answer API for lightweight searches
        without requiring API keys.

        Args:
            query: Search query string.
            num_results: Maximum number of results to return.

        Returns:
            List of dicts with title, url, and snippet.
        """
        # Encode query
        encoded_query = urllib.parse.urlencode({"q": query})
        url = f"https://api.duckduckgo.com/?{encoded_query}&format=json&no_html=1"

        try:
            ssl_context = ssl.create_default_context()
            req = urllib.request.Request(url, headers={
                "User-Agent": "NovaPilot/0.1 (AI Assistant)",
            })
            response = urllib.request.urlopen(
                req, timeout=self.timeout, context=ssl_context
            )
            data = json.loads(response.read().decode("utf-8"))

            results = []

            # Abstract (main answer)
            abstract = data.get("Abstract", "")
            abstract_url = data.get("AbstractURL", "")
            abstract_source = data.get("AbstractSource", "")
            if abstract:
                results.append({
                    "title": data.get("Heading", query),
                    "url": abstract_url,
                    "snippet": self._clean_html(abstract),
                    "source": abstract_source,
                })

            # Related topics
            topics = data.get("RelatedTopics", [])
            for topic in topics[:num_results]:
                if isinstance(topic, dict):
                    text = topic.get("Text", "")
                    url_link = topic.get("FirstURL", "")
                    if text and url_link:
                        results.append({
                            "title": topic.get("Text", "")[:80],
                            "url": url_link,
                            "snippet": self._clean_html(text),
                            "source": "",
                        })
                elif isinstance(topic, str):
                    # Skip category headers
                    continue

            # If no results from API, return a fallback
            if not results:
                results.append({
                    "title": "Search",
                    "url": f"https://duckduckgo.com/?q={urllib.parse.quote(query)}",
                    "snippet": f"No instant results found. "
                               f"Click to search DuckDuckGo for: {query}",
                    "source": "duckduckgo",
                })

            return results[:num_results]

        except urllib.error.URLError as e:
            return [{
                "title": "Search Error",
                "url": "",
                "snippet": f"Network error: {e.reason}",
                "source": "",
            }]
        except Exception as e:
            return [{
                "title": "Search Error",
                "url": "",
                "snippet": f"Search failed: {e}",
                "source": "",
            }]

    def fetch_url(self, url, extract_text=True):
        """Fetch content from a URL.

        Args:
            url: URL to fetch.
            extract_text: Whether to extract text content from HTML.

        Returns:
            Dict with 'url', 'title', 'content', and 'status' keys.
        """
        # Ensure URL has a scheme
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        try:
            ssl_context = ssl.create_default_context()
            req = urllib.request.Request(url, headers={
                "User-Agent": "NovaPilot/0.1 (AI Assistant)",
                "Accept": "text/html,application/json,text/plain,*/*",
            })
            response = urllib.request.urlopen(
                req, timeout=self.timeout, context=ssl_context
            )

            content_type = response.headers.get("Content-Type", "")
            raw_content = response.read(self.max_content_length)

            # Decode content
            encoding = "utf-8"
            if "charset=" in content_type:
                charset_match = re.search(
                    r'charset=([a-zA-Z0-9_-]+)', content_type
                )
                if charset_match:
                    encoding = charset_match.group(1)

            try:
                text_content = raw_content.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                text_content = raw_content.decode("utf-8", errors="replace")

            # Extract text from HTML if needed
            if extract_text and "text/html" in content_type:
                text_content = self._html_to_text(text_content)

            # Extract title
            title = self._extract_title(raw_content.decode(encoding, errors="replace"))

            return {
                "url": url,
                "title": title,
                "content": text_content[:self.max_content_length],
                "content_length": len(text_content),
                "status": "success",
            }

        except urllib.error.HTTPError as e:
            return {
                "url": url,
                "title": "",
                "content": f"HTTP Error {e.code}: {e.reason}",
                "status": "error",
            }
        except urllib.error.URLError as e:
            return {
                "url": url,
                "title": "",
                "content": f"Connection error: {e.reason}",
                "status": "error",
            }
        except Exception as e:
            return {
                "url": url,
                "title": "",
                "content": f"Failed to fetch URL: {e}",
                "status": "error",
            }

    def _html_to_text(self, html_content):
        """Convert HTML content to plain text.

        Removes HTML tags, scripts, styles, and decodes HTML entities.

        Args:
            html_content: Raw HTML string.

        Returns:
            Plain text string.
        """
        # Remove script and style blocks
        text = re.sub(
            r'<script[^>]*>.*?</script>',
            '', html_content, flags=re.DOTALL | re.IGNORECASE
        )
        text = re.sub(
            r'<style[^>]*>.*?</style>',
            '', text, flags=re.DOTALL | re.IGNORECASE
        )

        # Remove HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)

        # Decode HTML entities
        text = html.unescape(text)

        # Normalize whitespace
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n\n', text)

        return text.strip()

    def _extract_title(self, html_content):
        """Extract the title from HTML content.

        Args:
            html_content: HTML string.

        Returns:
            Title string, or empty string if not found.
        """
        match = re.search(
            r'<title[^>]*>(.*?)</title>',
            html_content, re.DOTALL | re.IGNORECASE
        )
        if match:
            title = html.unescape(match.group(1).strip())
            # Normalize whitespace
            title = re.sub(r'\s+', ' ', title)
            return title
        return ""

    def _clean_html(self, text):
        """Remove any remaining HTML tags from text.

        Args:
            text: Text potentially containing HTML.

        Returns:
            Cleaned text string.
        """
        text = re.sub(r'<[^>]+>', '', text)
        text = html.unescape(text)
        return text.strip()

    def format_search_results(self, results):
        """Format search results as a readable string.

        Args:
            results: List of result dicts from search().

        Returns:
            Formatted multi-line string.
        """
        if not results:
            return "No results found."

        lines = []
        for i, result in enumerate(results, 1):
            lines.append(f"{i}. {result.get('title', 'Untitled')}")
            if result.get("url"):
                lines.append(f"   {result['url']}")
            if result.get("snippet"):
                lines.append(f"   {result['snippet']}")
            lines.append("")

        return "\n".join(lines)

    def execute(self, args):
        """Execute web search or URL fetch (tool interface).

        Args:
            args: String query or dict with 'action' key.
                  Actions: search, fetch.

        Returns:
            Result string.
        """
        if isinstance(args, str):
            # Auto-detect if it's a URL or search query
            if re.match(r'https?://', args, re.IGNORECASE):
                args = {"action": "fetch", "url": args}
            else:
                args = {"action": "search", "query": args}

        action = args.get("action", "search")

        if action == "search":
            results = self.search(
                args.get("query", ""),
                num_results=args.get("num_results", 5),
            )
            return self.format_search_results(results)

        elif action == "fetch":
            result = self.fetch_url(
                args.get("url", ""),
                extract_text=args.get("extract_text", True),
            )
            if result["status"] == "success":
                lines = [
                    f"Title: {result['title']}",
                    f"URL: {result['url']}",
                    f"Length: {result['content_length']} chars",
                    "",
                    result["content"][:3000],
                ]
                if result["content_length"] > 3000:
                    lines.append(f"\n... (truncated, {result['content_length']} total chars)")
                return "\n".join(lines)
            else:
                return f"Error fetching URL: {result['content']}"

        else:
            return f"Unknown action: {action}. Use: search, fetch."
