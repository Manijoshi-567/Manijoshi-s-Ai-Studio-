import urllib.parse
import re
import requests
from bs4 import BeautifulSoup
from typing import Dict, Any, List

class WebScraper:
    def __init__(self, timeout: int = 20):
        self.timeout = timeout
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    def scrape_url(self, url: str) -> Dict[str, Any]:
        """Scrapes and extracts full page structure, text, and metadata from a target website URL."""
        if not url.startswith(("http://", "https://")):
            url = "https://" + url

        parsed_url = urllib.parse.urlparse(url)
        domain = parsed_url.netloc.replace("www.", "")

        try:
            response = requests.get(url, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            html_content = response.text
        except Exception as e:
            return {
                "success": False,
                "domain": domain,
                "url": url,
                "error": str(e),
                "title": domain.capitalize(),
                "description": f"Landing page concept for {domain}",
                "html_content": "",
                "headings": [],
                "paragraphs": [],
                "features": [],
                "images": [],
                "full_text": ""
            }

        soup = BeautifulSoup(html_content, "html.parser")

        # Extract title
        title = soup.title.string.strip() if soup.title and soup.title.string else domain

        # Extract meta description
        meta_desc = ""
        meta_tag = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
        if meta_tag and meta_tag.get("content"):
            meta_desc = meta_tag["content"].strip()

        # Extract headings
        headings = []
        for tag in ["h1", "h2", "h3"]:
            for h in soup.find_all(tag):
                text = h.get_text().strip()
                if text and len(text) > 3:
                    headings.append(f"[{tag.upper()}] {text}")

        # Extract main paragraphs
        paragraphs = []
        for p in soup.find_all("p"):
            text = p.get_text().strip()
            if text and len(text) > 15 and text not in paragraphs:
                paragraphs.append(text)

        # Extract list items
        features = []
        for li in soup.find_all("li"):
            text = li.get_text().strip()
            if text and 10 < len(text) < 150:
                features.append(text)

        # Extract images
        images = []
        for img in soup.find_all("img"):
            src = img.get("src")
            alt = img.get("alt", "")
            if src:
                full_src = urllib.parse.urljoin(url, src)
                images.append({"src": full_src, "alt": alt})

        # Process exact page clone HTML
        exact_html = self._build_exact_page_clone(soup, url)

        clean_text = soup.get_text(separator=" ", strip=True)
        clean_text = re.sub(r"\s+", " ", clean_text)[:4000]

        return {
            "success": True,
            "domain": domain,
            "url": url,
            "title": title,
            "description": meta_desc,
            "exact_html": exact_html,
            "headings": headings[:15],
            "paragraphs": paragraphs[:10],
            "features": features[:12],
            "images": images[:8],
            "full_text": clean_text
        }

    def _build_exact_page_clone(self, soup: BeautifulSoup, base_url: str) -> str:
        """Converts relative URLs in HTML into absolute URLs and injects <base> tag for exact visual fidelity."""
        # Ensure head tag exists
        if not soup.head:
            head = soup.new_tag("head")
            if soup.html:
                soup.html.insert(0, head)

        # Add <base href="..."> tag so all relative assets (images, fonts, css, js) resolve to the original site
        base_tag = soup.find("base")
        if not base_tag:
            base_tag = soup.new_tag("base", href=base_url)
            soup.head.insert(0, base_tag)

        # Remove frame-busting or redirect scripts
        for script in soup.find_all("script"):
            script_text = script.string or ""
            if "top.location" in script_text or "window.location" in script_text or "framebusting" in script_text.lower():
                script.decompose()

        # Remove restrictive meta Content-Security-Policy tags that block iframe rendering
        for meta in soup.find_all("meta"):
            if meta.get("http-equiv", "").lower() == "content-security-policy":
                meta.decompose()

        # Fix image src attributes to absolute URLs
        for img in soup.find_all("img"):
            if img.get("src"):
                img["src"] = urllib.parse.urljoin(base_url, img["src"])
            if img.get("srcset"):
                # Clean srcset relative links
                srcset_parts = img["srcset"].split(",")
                new_srcset = []
                for part in srcset_parts:
                    part_strip = part.strip().split(" ")
                    if part_strip and part_strip[0]:
                        part_strip[0] = urllib.parse.urljoin(base_url, part_strip[0])
                        new_srcset.append(" ".join(part_strip))
                img["srcset"] = ", ".join(new_srcset)

        # Fix link href attributes (stylesheets & favicons)
        for link in soup.find_all("link"):
            if link.get("href"):
                link["href"] = urllib.parse.urljoin(base_url, link["href"])

        # Fix script src attributes
        for script in soup.find_all("script"):
            if script.get("src"):
                script["src"] = urllib.parse.urljoin(base_url, script["src"])

        # Fix anchor links so they open in a new tab rather than inside the preview iframe
        for a in soup.find_all("a"):
            if a.get("href") and not a["href"].startswith("#") and not a["href"].startswith("javascript:"):
                a["href"] = urllib.parse.urljoin(base_url, a["href"])
                a["target"] = "_blank"

        return str(soup)
