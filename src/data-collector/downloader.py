"""Downloads photos from Bing's image search.

Bing does not offer this as an API: we read the page its image search loads, the way a browser does.
When Bing changes that page, this file is the one to fix.
"""

import io
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0 Safari/537.36"
}
PAGE_SIZE = 35  # results Bing returns per page
MAX_PAGES = 20  # stop looking after this many pages, even if we have too few photos


def fetch(url: str, timeout: int = 20) -> bytes:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def image_links(query: str, first: int) -> list[str]:
    """The photo addresses on one page of results, starting at result number `first`"""
    params = {"q": query, "first": first, "count": PAGE_SIZE, "adlt": "strict"}
    html = fetch("https://www.bing.com/images/async?" + urllib.parse.urlencode(params))
    return re.findall(r"murl&quot;:&quot;(.*?)&quot;", html.decode("utf-8", "replace"))


def download_images(query: str, folder: Path, limit: int) -> int:
    """Saves up to `limit` photos for `query` in `folder`. Returns how many it saved."""
    folder.mkdir(parents=True, exist_ok=True)
    seen: set[str] = set()
    saved = 0
    for page in range(MAX_PAGES):
        links = [link for link in image_links(query, page * PAGE_SIZE) if link not in seen]
        if not links:
            break
        for link in links:
            if saved >= limit:
                return saved
            seen.add(link)
            try:
                data = fetch(link)
                with Image.open(io.BytesIO(data)) as image:  # only keep what really is an image
                    image_format = (image.format or "jpeg").lower()
                    image.verify()
            except Exception as error:  # dead links, timeouts, HTML pages: skip them
                print(f"  skipped {link[:70]}: {error}")
                continue
            saved += 1
            (folder / f"{saved:03d}.{image_format}").write_bytes(data)
        time.sleep(1)  # be polite to Bing
    return saved
