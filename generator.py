import sys
import re
from pathlib import Path
from typing import Dict, Any, Optional

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console


from scraper import WebScraper
from llm import LLMClient
from agents import ProductStrategistAgent, CopywriterAgent, UIArchitectAgent
from builder import SiteBuilder

console = Console()

class LandingPageGenerator:
    def __init__(self, provider: str = "openai", model: str = None, api_key: str = None, output_dir: Path = Path("output")):
        self.llm_client = LLMClient(provider=provider, model=model, api_key=api_key)
        self.scraper = WebScraper()
        self.builder = SiteBuilder(output_dir=output_dir)

        # Initialize agents
        self.strategist = ProductStrategistAgent(self.llm_client)
        self.copywriter = CopywriterAgent(self.llm_client)
        self.architect = UIArchitectAgent(self.llm_client)

    def generate_from_url(self, url_or_concept: str, mode: str = "url", custom_instructions: str = "", target_device: str = "desktop", color_theme: str = "") -> Path:
        """Executes the complete multi-agent pipeline to generate a landing page from a URL or custom description."""
        console.print(f"[bold cyan]🔍 Step 1/4:[/bold cyan] Processing input in [gold1]'{mode.upper()}'[/gold1] mode for device [gold1]'{target_device.upper()}'[/gold1]...")

        combined_instructions = f"{custom_instructions}\nColor Theme: {color_theme}".strip() if color_theme else custom_instructions

        if mode == "url":
            site_data = self.scraper.scrape_url(url_or_concept)
            site_data["mode"] = "url"
            site_data["custom_instructions"] = combined_instructions
            site_data["color_theme"] = color_theme
        else:
            # Custom Description / Keyword Mode
            site_data = {
                "success": True,
                "domain": "custom_prompt",
                "mode": "description",
                "custom_instructions": combined_instructions,
                "color_theme": color_theme,
                "url": "",
                "title": url_or_concept,
                "description": url_or_concept,
                "headings": [url_or_concept],
                "paragraphs": [url_or_concept, combined_instructions],
                "features": [],
                "images": [],
                "full_text": f"{url_or_concept}\n{combined_instructions}"
            }

        console.print(f"[bold cyan]🧠 Step 2/4:[/bold cyan] Product Strategist Agent formulating positioning...")
        strategy = self.strategist.run(site_data)
        
        # Derive output domain slug from synthesized brand name
        brand_name = strategy.get("product_name", "landing_page")
        domain_slug = re.sub(r"[^\w]+", "_", brand_name.lower()).strip("_") or "landing_page"

        console.print(f"  └─ Brand Name: [bold gold1]{brand_name}[/bold gold1]")
        console.print(f"  └─ Tagline: {strategy.get('tagline', '')}")

        console.print(f"[bold cyan]✍️ Step 3/4:[/bold cyan] Copywriter Agent crafting high-converting section copy...")
        copy = self.copywriter.run(strategy)

        console.print(f"[bold cyan]🎨 Step 4/4:[/bold cyan] UI/UX Architect Agent generating landing page for [gold1]{target_device.upper()}[/gold1]...")
        
        # If in URL mode and exact HTML was scraped successfully
        if mode == "url" and site_data.get("exact_html"):
            if not custom_instructions:
                console.print(f"  └─ Rendering exact landing page clone for [bold gold1]{domain_slug}[/bold gold1]...")
                html_code = site_data["exact_html"]
            else:
                console.print(f"  └─ Applying custom AI tweaks to exact landing page clone...")
                html_code = self.architect.run_tweak(site_data["exact_html"], custom_instructions, target_device=target_device)
        else:
            html_code = self.architect.run(strategy, copy, target_device=target_device)

        # Save output
        output_filepath = self.builder.save_landing_page(domain_slug, html_code, strategy, copy)

        console.print(f"\n[bold green]✨ Landing Page generated successfully![/bold green]")
        console.print(f"📁 Output file: [underline]{output_filepath.resolve()}[/underline]\n")

        return output_filepath



