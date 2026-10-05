import json
import re
from typing import Dict, Any
from llm import LLMClient

class ProductStrategistAgent:
    """Agent 1: Analyzes scraped web content or concept and formulates positioning strategy."""
    
    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def run(self, raw_site_data: Dict[str, Any]) -> Dict[str, Any]:
        system_prompt = (
            "You are a Senior Product Marketing Strategist. "
            "Analyze the provided website information and synthesize a comprehensive product positioning strategy. "
            "Return your response ONLY as a clean JSON object without markdown formatting."
        )

        user_prompt = f"""
Input Title/Prompt: {raw_site_data.get('title')}
Website URL: {raw_site_data.get('url')}
Meta Description: {raw_site_data.get('description')}
Custom Instructions: {raw_site_data.get('custom_instructions')}
User Selected Color Theme: {raw_site_data.get('color_theme')}
Extracted Headings: {json.dumps(raw_site_data.get('headings', []))}
Extracted Paragraphs: {json.dumps(raw_site_data.get('paragraphs', []))}
Extracted Features: {json.dumps(raw_site_data.get('features', []))}

INTENT ANALYSIS & GENERATION RULES:
1. SINGLE BRAND KEYWORD INPUT (e.g. "Spotify", "Netflix", "Airbnb", "Tesla", "YouTube", "Stripe", "GitHub", "Linear", "Notion", "Discord", etc.):
   - Recognize the brand's core domain, target audience, signature color scheme, and key features.
   - Synthesize an authentic, high-converting landing page positioning strategy for that specific brand.
2. CUSTOM DETAILED DESCRIPTION PROMPT (e.g. "An AI Fitness Tracker App with workout logs and calorie counter", "Dark mode crypto trading bot"):
   - Analyze the user's explicit query requirements and infer implicit user needs.
   - Invent a short, catchy, professional brand name (e.g. "FitPulse AI", "CryptoBot Pro").
   - Create a tailored color palette (HEX primary, secondary, accent, bg_mode), tagline, value props, and 4 specific key features matching the user's prompt.
3. COLOR THEME OVERRIDE (MANDATORY):
   - If a "User Selected Color Theme" is provided (e.g. "cream_purple", "cyberpunk_neon", "emerald_tech", "indigo_saas", "sunset_amber"), you MUST override the "color_palette" in your JSON response to match that theme:
     * cream_purple: primary "#6818cd", secondary "#d4f937", bg_mode "dark"
     * cyberpunk_neon: primary "#00f2fe", secondary "#f000ff", bg_mode "dark"
     * emerald_tech: primary "#10b981", secondary "#06b6d4", bg_mode "dark"
     * indigo_saas: primary "#6366f1", secondary "#a855f7", bg_mode "dark"
     * sunset_amber: primary "#ff5e36", secondary "#f59e0b", bg_mode "dark"

Synthesize this into JSON with the following keys:
1. "product_name": Short punchy brand/product name
2. "tagline": One compelling sentence overview
3. "target_audience": Primary user persona
4. "brand_voice": Tone (e.g. Modern, Bold, Professional, Playful)
5. "color_palette": {{ "primary": "#hex", "secondary": "#hex", "accent": "#hex", "bg_mode": "dark" or "light" }}
6. "core_value_props": List of 3 core benefits
7. "key_features": List of 4 distinct key features with short descriptions
8. "primary_cta": Action button text (e.g. "Get Started Free", "Book a Demo")
"""

        raw_output = self.llm.generate(user_prompt, system_prompt, response_format="json")
        return self._clean_json(raw_output)

    def _clean_json(self, text: str) -> Dict[str, Any]:
        text = re.sub(r"^```json\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"^```\s*", "", text, flags=re.MULTILINE)
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            return {"raw_strategy": text}


class CopywriterAgent:
    """Agent 2: Converts positioning strategy into structured, high-converting landing page copy."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def run(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        system_prompt = (
            "You are a World-Class Conversion Copywriter for SaaS and Tech Products. "
            "Using the product positioning strategy, write high-converting, persuasive copy for all landing page sections. "
            "Return your response ONLY as a clean JSON object."
        )

        user_prompt = f"""
Product Strategy:
{json.dumps(strategy, indent=2)}

Generate structured JSON containing:
1. "nav": {{ "brand_name": "...", "links": ["Features", "How it Works", "Testimonials", "Pricing", "FAQ"], "cta": "..." }}
2. "hero": {{ "badge": "...", "headline": "...", "subheadline": "...", "primary_cta": "...", "secondary_cta": "...", "trust_metric": "..." }}
3. "features": [
     {{ "title": "...", "description": "...", "icon": "sparkles" }},
     {{ "title": "...", "description": "...", "icon": "zap" }},
     {{ "title": "...", "description": "...", "icon": "shield-check" }},
     {{ "title": "...", "description": "...", "icon": "bar-chart" }}
   ]
4. "how_it_works": [
     {{ "step": "01", "title": "...", "description": "..." }},
     {{ "step": "02", "title": "...", "description": "..." }},
     {{ "step": "03", "title": "...", "description": "..." }}
   ]
5. "testimonials": [
     {{ "quote": "...", "author": "...", "role": "...", "company": "...", "avatar_initials": "..." }},
     {{ "quote": "...", "author": "...", "role": "...", "company": "...", "avatar_initials": "..." }}
   ]
6. "pricing": [
     {{ "name": "Starter", "price": "$29/mo", "description": "Perfect for individuals and small teams", "features": ["...", "..."], "highlighted": false, "cta": "Start Free Trial" }},
     {{ "name": "Pro", "price": "$79/mo", "description": "For growing companies needing advanced power", "features": ["...", "...", "..."], "highlighted": true, "cta": "Get Pro Now" }}
   ]
7. "faq": [
     {{ "question": "...", "answer": "..." }},
     {{ "question": "...", "answer": "..." }},
     {{ "question": "...", "answer": "..." }}
   ]
8. "footer_cta": {{ "headline": "...", "subheadline": "...", "button": "..." }}
"""

        raw_output = self.llm.generate(user_prompt, system_prompt, response_format="json")
        return self._clean_json(raw_output)

    def _clean_json(self, text: str) -> Dict[str, Any]:
        text = re.sub(r"^```json\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"^```\s*", "", text, flags=re.MULTILINE)
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            return {"raw_copy": text}


class UIArchitectAgent:
    """Agent 3: Takes copy and strategy to construct premium HTML5/CSS/JS frontend code optimized for target device."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def run(self, strategy: Dict[str, Any], copy: Dict[str, Any], target_device: str = "desktop") -> str:
        system_prompt = (
            f"You are a Principal Frontend Architect and Mobile/Web Designer. "
            f"You produce stunning, responsive HTML5 + CSS3 + JS single-page web applications "
            f"specifically optimized for a target device viewport: '{target_device.upper()}'. "
            "Apply modern aesthetics: glassmorphism, gradient accents, Google Fonts (Outfit / Inter), "
            "responsive layout, micro-animations, mobile drawer navigation, and interactive FAQ toggles. "
            "Return ONLY the complete raw HTML code starting with <!DOCTYPE html>."
        )

        user_prompt = f"""
Target Device Viewport: {target_device.upper()} (Optimize layout, typography, padding, and navigation for {target_device})

Product Strategy:
{json.dumps(strategy, indent=2)}

Copywriting Content:
{json.dumps(copy, indent=2)}

Create a complete, single-file production-ready HTML document.
Requirements:
1. Include modern embedded CSS in <style> tag with standard variables for primary, secondary, background, and text colors based on the color palette.
2. Include Google Font 'Outfit' or 'Inter'.
3. Use Lucide icons (via CDN script <script src="https://unpkg.com/lucide@latest"></script>) or SVG inline icons.
4. Include responsive Header/Navbar tailored for {target_device}.
5. Hero Section with gradient badge, glowing CTA buttons, and preview card.
6. Grid for Features with subtle hover elevation effects.
7. Step-by-step 'How It Works' workflow section.
8. Testimonials carousel or grid.
9. Pricing table with highlighted 'Popular' badge.
10. Interactive FAQ Accordion section (using simple Vanilla JS toggle script included in <script> tag).
11. High-impact Footer CTA banner and clean footer links.
12. Ensure layout is specifically tailored for {target_device} screen sizes.
"""

        raw_output = self.llm.generate(user_prompt, system_prompt)
        return self._extract_html(raw_output)

    def run_tweak(self, exact_html: str, custom_instructions: str, target_device: str = "desktop") -> str:
        """Applies custom user tweak instructions while maintaining original HTML structure and target device optimization."""
        system_prompt = (
            f"You are a Senior Frontend Engineer. "
            f"Modify the provided exact HTML document according to user instructions, "
            f"ensuring optimal rendering for target device viewport: '{target_device.upper()}'. "
            "Preserve the overall DOM structure, CSS link references, fonts, images, and layout. "
            "Return ONLY the modified HTML code starting with <!DOCTYPE html>."
        )

        user_prompt = f"""
Target Device: {target_device.upper()}
Instructions: {custom_instructions}

Original HTML (capped snippet):
{exact_html[:8000]}
"""
        raw_output = self.llm.generate(user_prompt, system_prompt)
        cleaned = self._extract_html(raw_output)
        return cleaned if cleaned.startswith("<") else exact_html

    def _extract_html(self, text: str) -> str:
        text = re.sub(r"^```html\s*", "", text, flags=re.MULTILINE)
        text = re.sub(r"^```\s*", "", text, flags=re.MULTILINE)
        return text.strip()


