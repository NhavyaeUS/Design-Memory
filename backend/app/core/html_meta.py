"""
HTML metadata parsing utilities — Milestone 1B.2.

Extracts titles, descriptions, favicons, and preview images from HTML text.
Uses Python's standard library html.parser to remain dependency-free, robust,
and fast.
"""
import html
from html.parser import HTMLParser
from typing import Dict, List, Optional
from urllib.parse import urljoin, urlparse

from app.core.urls import extract_domain


class ExtractedMetadata:
    """Structured result of HTML metadata extraction."""

    def __init__(
        self,
        base_url: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        favicon_url: Optional[str] = None,
        image_url: Optional[str] = None,
    ):
        self.base_url = base_url
        self.title = title
        self.description = description
        self.favicon_url = favicon_url
        self.image_url = image_url

    def to_dict(self) -> Dict[str, Optional[str]]:
        return {
            "base_url": self.base_url,
            "title": self.title,
            "description": self.description,
            "favicon_url": self.favicon_url,
            "image_url": self.image_url,
        }


def _clean_text(text: Optional[str], max_len: Optional[int] = None) -> Optional[str]:
    """Unescape HTML entities, collapse redundant whitespace, and truncate if needed."""
    if not text:
        return None
    unescaped = html.unescape(text)
    collapsed = " ".join(unescaped.split())
    if not collapsed:
        return None
    if max_len and len(collapsed) > max_len:
        return collapsed[:max_len].rstrip()
    return collapsed


class _HTMLMetaParser(HTMLParser):
    """Event-driven parser extracting title, meta tags, and icon links."""

    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self._in_title = False
        self._title_chunks: List[str] = []

        self.tag_title: Optional[str] = None
        self.og_title: Optional[str] = None
        self.twitter_title: Optional[str] = None

        self.meta_desc: Optional[str] = None
        self.og_desc: Optional[str] = None
        self.twitter_desc: Optional[str] = None

        self.icon_url: Optional[str] = None
        self.apple_icon_url: Optional[str] = None
        self.og_image: Optional[str] = None

    def handle_starttag(self, tag: str, attrs: List[tuple]):
        tag_lower = tag.lower()
        attr_dict = {k.lower(): (v or "") for k, v in attrs}

        if tag_lower == "title":
            self._in_title = True

        elif tag_lower == "meta":
            prop = (attr_dict.get("property") or attr_dict.get("name") or "").lower().strip()
            content = attr_dict.get("content", "").strip()
            if not content:
                return

            if prop == "og:title" and not self.og_title:
                self.og_title = content
            elif prop == "twitter:title" and not self.twitter_title:
                self.twitter_title = content
            elif prop == "description" and not self.meta_desc:
                self.meta_desc = content
            elif prop == "og:description" and not self.og_desc:
                self.og_desc = content
            elif prop == "twitter:description" and not self.twitter_desc:
                self.twitter_desc = content
            elif prop == "og:image" and not self.og_image:
                self.og_image = urljoin(self.base_url, content)
            elif prop == "twitter:image" and not self.og_image:
                self.og_image = urljoin(self.base_url, content)

        elif tag_lower == "link":
            rel_str = attr_dict.get("rel", "").lower()
            rel_tokens = set(rel_str.split())
            href = attr_dict.get("href", "").strip()
            if not href:
                return

            full_href = urljoin(self.base_url, href)
            if "icon" in rel_tokens or "shortcut" in rel_tokens:
                if not self.icon_url or "icon" in rel_tokens:
                    self.icon_url = full_href
            elif "apple-touch-icon" in rel_tokens and not self.apple_icon_url:
                self.apple_icon_url = full_href

    def handle_endtag(self, tag: str):
        if tag.lower() == "title":
            self._in_title = False
            if self._title_chunks and not self.tag_title:
                self.tag_title = "".join(self._title_chunks).strip()

    def handle_data(self, data: str):
        if self._in_title:
            self._title_chunks.append(data)


def extract_meta_from_html(html_content: str, base_url: str) -> ExtractedMetadata:
    """
    Parse HTML content and extract standard webpage metadata.
    Prioritizes OpenGraph tags while cleanly falling back to standard HTML tags.
    """
    parser = _HTMLMetaParser(base_url)
    try:
        parser.feed(html_content)
        parser.close()
    except Exception:
        # html.parser is forgiving, but even in extreme malformed HTML cases,
        # we don't crash — we return whatever was parsed so far.
        pass

    # In case <title> was never closed with </title> before end of document
    if parser._title_chunks and not parser.tag_title:
        parser.tag_title = "".join(parser._title_chunks).strip()

    # Title resolution: og:title > <title> > twitter:title
    resolved_title = _clean_text(
        parser.og_title or parser.tag_title or parser.twitter_title,
        max_len=500,
    )

    # Description resolution: og:description > meta[name=description] > twitter:description
    resolved_desc = _clean_text(
        parser.og_desc or parser.meta_desc or parser.twitter_desc,
        max_len=1000,
    )

    # Favicon resolution: link[rel=icon] > link[rel=apple-touch-icon] > default /favicon.ico
    resolved_favicon = parser.icon_url or parser.apple_icon_url
    if not resolved_favicon:
        try:
            parsed = urlparse(base_url)
            if parsed.scheme and parsed.netloc:
                resolved_favicon = f"{parsed.scheme}://{parsed.netloc}/favicon.ico"
        except Exception:
            resolved_favicon = None

    return ExtractedMetadata(
        base_url=base_url,
        title=resolved_title,
        description=resolved_desc,
        favicon_url=resolved_favicon,
        image_url=parser.og_image,
    )
