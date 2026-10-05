import json
import re
import requests
import urllib.parse
from typing import Dict, Any, Optional
from config import Config

class LLMClient:
    def __init__(self, provider: str = None, model: str = None, api_key: str = None):
        # Resolve provider intelligently based on available environment variables
        resolved_provider = Config.get_available_provider(provider)
        self.provider = resolved_provider.lower()
        self.api_key = api_key or Config.get_api_key(self.provider)

        # Ensure model is valid for the resolved provider
        if not model or (self.provider == "gemini" and "gpt" in str(model).lower()) or (self.provider == "openai" and "gemini" in str(model).lower()):
            self.model = Config.get_default_model(self.provider)
        else:
            self.model = model

    def generate(self, prompt: str, system_prompt: str = "You are an expert AI assistant.", response_format: Optional[str] = None) -> str:
        """Generates completion using the selected LLM provider or smart site-aware engine if key is missing."""
        if not self.api_key and self.provider != "ollama":
            return self._fallback_generate(prompt, system_prompt, response_format)

        try:
            if self.provider == "openai":
                return self._call_openai(prompt, system_prompt, response_format)
            elif self.provider == "gemini":
                return self._call_gemini(prompt, system_prompt)
            elif self.provider == "anthropic":
                return self._call_anthropic(prompt, system_prompt)
            elif self.provider == "ollama":
                return self._call_ollama(prompt, system_prompt)
            else:
                return self._fallback_generate(prompt, system_prompt, response_format)
        except Exception as e:
            print(f"⚠️ API call to {self.provider} failed ({e}). Switching to Smart Semantic Query Engine...")
            return self._fallback_generate(prompt, system_prompt, response_format)

    def _call_openai(self, prompt: str, system_prompt: str, response_format: Optional[str] = None) -> str:
        import openai
        client = openai.OpenAI(api_key=self.api_key)
        kwargs = {
            "model": self.model or "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.7
        }
        if response_format == "json":
            kwargs["response_format"] = {"type": "json_object"}

        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    def _call_gemini(self, prompt: str, system_prompt: str) -> str:
        models_to_try = [self.model or "gemini-1.5-flash", "gemini-2.0-flash", "gemini-1.5-pro"]
        models_to_try = list(dict.fromkeys(models_to_try))
        
        last_error = None
        for m in models_to_try:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={self.api_key}"
                payload = {
                    "contents": [
                        {"role": "user", "parts": [{"text": f"{system_prompt}\n\n{prompt}"}]}
                    ]
                }
                res = requests.post(url, json=payload, timeout=60)
                res.raise_for_status()
                data = res.json()
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except Exception as e:
                last_error = e
                continue
        raise last_error

    def _call_anthropic(self, prompt: str, system_prompt: str) -> str:
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = {
            "model": self.model or "claude-3-5-sonnet-20241022",
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}]
        }
        res = requests.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload, timeout=60)
        res.raise_for_status()
        return res.json()["content"][0]["text"]

    def _call_ollama(self, prompt: str, system_prompt: str) -> str:
        url = f"{Config.OLLAMA_BASE_URL}/api/generate"
        payload = {
            "model": self.model or "llama3",
            "prompt": f"{system_prompt}\n\n{prompt}",
            "stream": False
        }
        res = requests.post(url, json=payload, timeout=120)
        res.raise_for_status()
        return res.json()["response"]

    def _fallback_generate(self, prompt: str, system_prompt: str, response_format: Optional[str] = None) -> str:
        """Smart semantic engine that analyzes user queries and builds domain-tailored responses."""
        intent = self._analyze_query_intent(prompt)
        
        # Detect target device from prompt
        device_match = re.search(r"Target Device(?: Viewport)?:\s*(\w+)", prompt, re.IGNORECASE)
        target_device = device_match.group(1).lower() if device_match else "desktop"

        # Extract strategy JSON if present in prompt (from ProductStrategistAgent output)
        strat_match = re.search(r"Product Strategy:\s*(\{[\s\S]*?\})\s*(?:Copywriting Content:|Generate structured JSON|\n\n)", prompt)
        if strat_match:
            try:
                strat = json.loads(strat_match.group(1))
                if isinstance(strat, dict):
                    intent.update(strat)
            except Exception:
                pass

        if "Principal Frontend Architect" in system_prompt or "HTML document" in prompt:
            return self._build_dynamic_html(intent, target_device=target_device)
        elif "Copywriter" in system_prompt or "Copywriting Content" in prompt:
            brand_name = intent.get("product_name", "Modern Brand")
            headline = intent.get("headline", f"Discover the Art of {brand_name}")
            hero_badge = intent.get("hero_badge", f"✨ Handcrafted Quality • {brand_name}")
            tagline = intent.get("tagline", "Crafted with passion and uncompromising attention to detail.")
            features = intent.get("key_features", [])
            pricing = intent.get("pricing", [])
            testimonials = intent.get("testimonials", [
                { "quote": f"{brand_name} completely transformed our daily experience. The quality and craftsmanship are unforgettable!", "author": "Sarah Jenkins", "role": "Creative Director", "company": "Studio Apex", "avatar_initials": "SJ" },
                { "quote": "Authentic, elegant, and exceptional in every way. Cannot recommend it enough!", "author": "David Chen", "role": "Lifestyle Editor", "company": "Vogue Review", "avatar_initials": "DC" }
            ])
            primary_cta = intent.get("primary_cta", "Explore Collection")

            return json.dumps({
                "nav": { "brand_name": brand_name, "links": ["Story", "Features", "Pricing", "FAQ"], "cta": primary_cta },
                "hero": {
                    "badge": hero_badge,
                    "headline": headline,
                    "subheadline": tagline,
                    "primary_cta": primary_cta,
                    "secondary_cta": "Learn Our Story",
                    "trust_metric": f"Loved by thousands of passionate customers and enthusiasts"
                },
                "features": features,
                "how_it_works": [
                    { "step": "01", "title": "Artisanal Sourcing & Craft", "description": "Only the finest materials and methods, carefully chosen without shortcuts." },
                    { "step": "02", "title": "Bespoke Preparation", "description": "Every detail tuned, polished, and perfected for an elevated sensory experience." },
                    { "step": "03", "title": "Delivered to Perfection", "description": "Enjoy seamless quality and memorable moments every single time." }
                ],
                "testimonials": testimonials,
                "pricing": pricing,
                "faq": intent.get("faq", [
                    { "question": f"What sets {brand_name} apart?", "answer": tagline },
                    { "question": f"How do I experience {brand_name}?", "answer": f"Click '{primary_cta}' to get started or place your order today." },
                    { "question": "Is this experience fully accessible across devices?", "answer": "Yes! Every detail is responsive and beautifully formatted for all viewports." }
                ]),
                "footer_cta": { "headline": f"Ready to experience {brand_name}?", "subheadline": "Join our community and savor the difference today.", "button": primary_cta }
            })
        else:
            # Return Product Strategist JSON
            return json.dumps(intent)

    def _analyze_query_intent(self, prompt: str) -> Dict[str, Any]:
        """Parses and analyzes prompt keywords, extracts industry domain, and synthesizes tailored concepts."""
        COLOR_THEMES = {
            "cream_purple": { "primary": "#6818cd", "secondary": "#d4f937", "bg_mode": "dark" },
            "cyberpunk_neon": { "primary": "#00f2fe", "secondary": "#f000ff", "bg_mode": "dark" },
            "emerald_tech": { "primary": "#10b981", "secondary": "#06b6d4", "bg_mode": "dark" },
            "indigo_saas": { "primary": "#6366f1", "secondary": "#a855f7", "bg_mode": "dark" },
            "sunset_amber": { "primary": "#ff5e36", "secondary": "#f59e0b", "bg_mode": "dark" }
        }

        # Check if user explicitly selected a color theme in prompt
        theme_match = re.search(r"Color Theme:\s*([\w_]+)", prompt, re.IGNORECASE)
        selected_theme = theme_match.group(1).lower() if theme_match else ""

        if not selected_theme:
            for theme_key in COLOR_THEMES:
                if theme_key in prompt.lower():
                    selected_theme = theme_key
                    break

        # Check if prompt contains Product Strategy JSON from a previous agent step
        prod_name_match = re.search(r'"product_name":\s*"([^"]+)"', prompt)
        title_match = re.search(r"(?:Website Title|Input Title/Prompt):\s*(.*)", prompt)
        url_match = re.search(r"Website URL:\s*(.*)", prompt)
        desc_match = re.search(r"Meta Description:\s*(.*)", prompt)

        raw_query = ""
        if prod_name_match and prod_name_match.group(1).strip():
            raw_query = prod_name_match.group(1).strip()
        elif title_match and title_match.group(1).strip():
            raw_query = title_match.group(1).strip()
        elif url_match and url_match.group(1).strip():
            raw_query = url_match.group(1).strip()
        else:
            raw_query = prompt.split("\n")[0].strip()

        # Clean raw query
        clean_raw = re.sub(r"^https?://(www\.)?", "", raw_query, flags=re.IGNORECASE)
        clean_raw = clean_raw.split("/")[0].strip()
        clean_query = clean_raw.lower()

        # Helper for word-boundary matching
        def has_kw(word_list: list) -> bool:
            pattern = r'\b(' + '|'.join(re.escape(k) for k in word_list) + r')\b'
            return bool(re.search(pattern, clean_query, re.IGNORECASE))

        # Detect Aesthetic and Tone Modifiers
        is_minimalist = has_kw(["minimalist", "minimalism", "minimal", "clean", "simple", "zen", "scandinavian"])

        # Check for well-known tech brands first
        KNOWN_BRANDS = {
            "spotify": {
                "product_name": "Spotify",
                "headline": "Listening Is Everything. 80M+ Songs.",
                "hero_badge": "🎵 80M+ Songs • Ad-Free Playback",
                "tagline": "Millions of songs, curated playlists, and exclusive podcasts on every device.",
                "target_audience": "Music enthusiasts, podcast listeners, and creators globally",
                "brand_voice": "Vibrant, Iconic, and Energetic",
                "color_palette": { "primary": "#1db954", "secondary": "#191414", "accent": "#1ed760", "bg_mode": "dark" },
                "core_value_props": ["80M+ High Quality Songs", "Personalized Daily Mixes", "Cross-Device Music Hand-off"],
                "key_features": [
                    { "title": "80M+ Ultra HD Songs", "description": "Stream unlimited tracks, albums, and curated playlists with pristine acoustics.", "icon": "music" },
                    { "title": "Personalized Daily Mixes", "description": "AI recommendation engine tuned to your exact listening habits and mood.", "icon": "sparkles" },
                    { "title": "Podcast & Video Shows", "description": "Tune into top global podcasts, creator livestreams, and original shows.", "icon": "radio" },
                    { "title": "Cross-Device Hand-Off", "description": "Seamlessly transfer playback between phone, desktop, car, and home speakers.", "icon": "smartphone" }
                ],
                "primary_cta": "Get Spotify Free",
                "pricing": [
                    { "name": "Free Tier", "price": "$0/mo", "description": "Shuffle play with occasional ads", "features": ["Basic Audio Streaming", "Playlist Creation", "Standard Quality Audio"], "highlighted": False, "cta": "Get Spotify Free" },
                    { "name": "Premium Individual", "price": "$10.99/mo", "description": "100% ad-free music with offline listening", "features": ["100% Ad-Free Audio", "Offline Downloads", "Unlimited Skips", "Lossless High Fidelity"], "highlighted": True, "cta": "Start 1 Month Free" }
                ]
            },
            "netflix": {
                "product_name": "Netflix",
                "headline": "Watch Anywhere. Cancel Anytime.",
                "hero_badge": "🎬 Unlimited 4K Movies & Original Series",
                "tagline": "Blockbuster films, award-winning documentaries, and binge-worthy series on demand.",
                "target_audience": "Entertainment lovers, families, and movie buffs",
                "brand_voice": "Cinematic, Bold, and Immersive",
                "color_palette": { "primary": "#e50914", "secondary": "#141414", "accent": "#b81d24", "bg_mode": "dark" },
                "core_value_props": ["Unlimited 4K Content", "Personalized Profiles", "Offline Downloads"],
                "key_features": [
                    { "title": "Unlimited 4K HDR Streaming", "description": "Watch thousands of blockbuster movies, award-winning series, and original documentaries.", "icon": "tv" },
                    { "title": "Personalized AI Profiles", "description": "Smart profile recommendations for every family member, including safe kids zone.", "icon": "sparkles" },
                    { "title": "Download & Watch Offline", "description": "Save your favorite movies and shows to watch on flights or daily commutes.", "icon": "download" },
                    { "title": "Cross-Platform Sync", "description": "Pick up right where you paused on phone, tablet, smart TV, or laptop.", "icon": "monitor" }
                ],
                "primary_cta": "Get Started",
                "pricing": [
                    { "name": "Standard with Ads", "price": "$6.99/mo", "description": "Full HD streaming with light ads", "features": ["Full HD 1080p", "Watch on 2 Devices", "Most Movies & Shows"], "highlighted": False, "cta": "Choose Standard" },
                    { "name": "Premium Ultra HD", "price": "$22.99/mo", "description": "4K Ultra HD + HDR + Spatial Audio", "features": ["4K Ultra HD & HDR", "Watch on 4 Devices Simultaneously", "Spatial Audio", "Download on 6 Devices"], "highlighted": True, "cta": "Choose Premium" }
                ]
            }
        }

        result_intent = None
        for key, data in KNOWN_BRANDS.items():
            if key in clean_query:
                result_intent = json.loads(json.dumps(data))
                break

        # SEMANTIC DOMAIN ONTOLOGY & KEYWORD RECOGNITION
        if not result_intent:
            # 1. COFFEE / CAFE / ROASTERY / BAKERY
            if has_kw(["coffee", "cafe", "espresso", "latte", "cappuccino", "roast", "roastery", "brew", "brews", "beans", "barista", "bakery", "mocha", "tea", "matcha", "croissant"]):
                brand_name = "Komorebi Artisan Coffee" if is_minimalist else "Velvet Roastworks"
                headline = "Simplicity in Every Cup. Handcrafted Artisan Coffee." if is_minimalist else "Hot, Delicious & Freshly Roasted Artisan Coffee."
                tagline = "Single-origin micro-lot beans, velvety espresso, and a tranquil minimalist space crafted for slow mornings."
                hero_badge = "☕ Hand-Roasted Daily • Single-Origin Micro-Lots"
                primary = "#3d2314" if is_minimalist else "#c87d55"
                secondary = "#e6ccb2" if is_minimalist else "#f7ede2"
                bg_mode = "dark" if not is_minimalist else "light"
                primary_cta = "Explore Coffee Menu"
                features = [
                    { "title": "Ethically Sourced Single-Origin Beans", "description": "Directly traded from smallholder organic farms in Ethiopia, Colombia, and Guatemala, roasted in micro-batches.", "icon": "coffee" },
                    { "title": "Master Barista Pour-Overs & Espresso", "description": "Precision temperature brewing, hand-poured Chemex, and velvety microfoam crafted to delicious perfection.", "icon": "flame" },
                    { "title": "Warm & Delicious Daily Pastries", "description": "Flaky French butter croissants, artisan sourdough, and warm cinnamon swirls baked fresh every morning.", "icon": "heart" },
                    { "title": "Serene Minimalist Atmosphere", "description": "Natural oak timber, soothing ambient warmth, and unhurried negative space designed to calm your soul.", "icon": "sparkles" }
                ]
                pricing = [
                    { "name": "Morning Tasting Ritual", "price": "$12", "description": "Specialty single-origin pour-over paired with warm artisanal pastry", "features": ["Choice of Single-Origin Roast", "Fresh Baked Daily Croissant", "Comfortable Minimalist Seating"], "highlighted": False, "cta": "Reserve Table" },
                    { "name": "Roaster's Club Subscription", "price": "$28/mo", "description": "Two 12oz bags of freshly roasted whole beans delivered to your doorstep", "features": ["Shipped within 24h of Roasting", "Ethically Sourced Micro-Lots", "Free Nationwide Shipping", "Curated Cupping Notes"], "highlighted": True, "cta": "Join the Club" },
                    { "name": "Barista Masterclass", "price": "$65", "description": "Hands-on 2-hour espresso extraction and latte art workshop", "features": ["Dialing-In Espresso Clinic", "Milk Steaming & Latte Art", "Complimentary 250g Bean Bag", "Barista Handbook"], "highlighted": False, "cta": "Book Workshop" }
                ]
                testimonials = [
                    { "quote": "The most peaceful coffee sanctuary in town. The Ethiopian pour-over is floral, sweet, and unforgettable.", "author": "Maya Lin", "role": "Food & Architecture Critic", "company": "Metropolitan Living", "avatar_initials": "ML" },
                    { "quote": "Pure minimalist perfection — no distractions, warm pastries, and extraordinary espresso.", "author": "Julian Vance", "role": "Barista Guild Champion", "company": "Specialty Coffee Review", "avatar_initials": "JV" }
                ]
                faq = [
                    { "question": "Where are your coffee beans sourced?", "answer": "We source 100% directly from smallholder organic farms with fair-trade price transparency, ensuring living wages for growers." },
                    { "question": "Do you offer non-dairy milk alternatives?", "answer": "Yes! We make homemade oat milk, organic almond milk, and pistachio milk fresh each morning with zero refined sugars." },
                    { "question": "Can I purchase whole beans for home brewing?", "answer": "Yes, all our seasonal single-origin roasts are available in whole bean or custom-ground for Chemex, Aeropress, or Espresso." }
                ]

            # 2. CARS / AUTOMOTIVE / SUPERCARS / EV
            elif has_kw(["car", "cars", "automobile", "automobiles", "vehicle", "vehicles", "supercar", "supercars", "sports car", "hypercar", "horsepower", "speed", "racing", "motor", "motors", "engine", "engines", "ev", "driving", "torque", "exhaust"]):
                brand_name = "Apex GT Velocity"
                headline = "Pure Adrenaline. 850 HP Precision Engineering."
                tagline = "Bred for the circuit, sculpted for the road. Uncompromising twin-turbo horsepower, carbon aerodynamics, and pure driving exhilaration."
                hero_badge = "🏎️ 0-60 mph in 2.5s • 850 Horsepower V8"
                primary = "#ef4444"
                secondary = "#f59e0b"
                bg_mode = "dark"
                primary_cta = "Schedule Track Test Drive"
                features = [
                    { "title": "850 HP Twin-Turbo V8 Engine", "description": "Hand-assembled powertrain producing 850 horsepower and 800 lb-ft of torque for blistering top speeds.", "icon": "gauge" },
                    { "title": "Active Carbon Aerodynamics", "description": "Ultra-lightweight chassis with adaptive wings delivering 600kg of downforce at triple-digit speeds.", "icon": "shield-check" },
                    { "title": "Track-Tuned Ceramic Brakes", "description": "Motorsport-grade carbon-ceramic discs ensuring fade-free stopping power under high track heat.", "icon": "disc" },
                    { "title": "Bespoke Alcantara Cockpit", "description": "Ergonomic racing seats, tactile paddle shifters, and real-time digital telemetry focused entirely on the driver.", "icon": "activity" }
                ]
                pricing = [
                    { "name": "Track Experience Day", "price": "$499", "description": "Full day track access with telemetry coaching and 10 hot laps", "features": ["Professional Instructor Coaching", "10 High-Speed Track Laps", "Full 4K In-Car Telemetry", "VIP Pit Lane Access"], "highlighted": False, "cta": "Book Track Day" },
                    { "name": "Apex GT Production Edition", "price": "$145,000", "description": "Street-legal track weapon with sport suspension and active aero", "features": ["850 HP Twin-Turbo Powertrain", "Carbon-Ceramic Brake System", "Active Aero Spoilers", "3-Year Factory Track Warranty"], "highlighted": True, "cta": "Configure Build" },
                    { "name": "Carbon Bespoke Unlimited", "price": "$210,000", "description": "One-of-one custom livery, titanium exhaust, and stripped race cabin", "features": ["Exposed Carbon Bodywork", "Titanium Race Exhaust System", "Custom Alcantara Interior Stitching", "Factory Delivery Experience"], "highlighted": False, "cta": "Inquire with Specialist" }
                ]
                testimonials = [
                    { "quote": "The throttle response is instantaneous and the chassis balance is telepathic. It redefines what 850 horsepower feels like.", "author": "Marcus Thorne", "role": "FIA GT Driver", "company": "Apex Motorsport", "avatar_initials": "MT" },
                    { "quote": "A masterclass in modern aerodynamics and acoustic drama. Unrivaled track weapon.", "author": "Helena Ross", "role": "Automotive Journalist", "company": "TopGear Performance", "avatar_initials": "HR" }
                ]
                faq = [
                    { "question": "What is the 0-60 acceleration and top speed?", "answer": "The Apex GT accelerates from 0-60 mph in 2.5 seconds with launch control and reaches an electronically governed top speed of 215 mph." },
                    { "question": "Is the vehicle street-legal?", "answer": "Yes, all production models are fully street-legal with DOT/EU compliance and feature a hydraulic front-axle lift for city streets." },
                    { "question": "How do I schedule a track test drive?", "answer": "Click 'Schedule Track Test Drive' above and our concierge will coordinate a private circuit session at your nearest certified track." }
                ]

            # 3. AMAZON / E-COMMERCE / MARKETPLACE / RETAIL
            elif has_kw(["amazon", "ecommerce", "e-commerce", "shop", "shops", "store", "stores", "marketplace", "retail", "cart", "shopping", "products", "gadgets", "deals"]):
                brand_name = "PrimeMart Global"
                headline = "Millions of Products. Delivered to Your Door in Hours."
                tagline = "Discover unbeatable deals on trending electronics, home essentials, and fashion with guaranteed authenticity and lightning-fast Prime delivery."
                hero_badge = "📦 Free Same-Day Delivery • 30-Day Easy Returns"
                primary = "#ff9900"
                secondary = "#146eb4"
                bg_mode = "dark"
                primary_cta = "Start Shopping Deals"
                features = [
                    { "title": "Lightning Same-Day Delivery", "description": "Enjoy free doorstep delivery on over 10 million eligible items with real-time GPS courier tracking.", "icon": "truck" },
                    { "title": "Curated Top-Rated Brands", "description": "Every item is verified for authenticity and backed by millions of genuine verified customer reviews.", "icon": "award" },
                    { "title": "Instant 1-Click Secure Checkout", "description": "Zero-friction payment encrypted with bank-level security and automated fraud protection.", "icon": "shield-check" },
                    { "title": "Hassle-Free 30-Day Returns", "description": "Prepaid return labels and instant refunds with drop-off at thousands of local pickup lockers.", "icon": "refresh-cw" }
                ]
                pricing = [
                    { "name": "Standard Shopper", "price": "Free", "description": "Basic access to daily deals and marketplace catalog", "features": ["Standard 3-5 Day Shipping", "Access to Flash Sales", "Standard Customer Support"], "highlighted": False, "cta": "Create Free Account" },
                    { "name": "Prime VIP Member", "price": "$14.99/mo", "description": "Unlimited free same-day shipping, exclusive deals & streaming", "features": ["Free Unlimited Same-Day Shipping", "Early Access to Lightning Deals", "Included Video & Music Streaming", "Exclusive 10% Member Cash Back"], "highlighted": True, "cta": "Start 30-Day Free Trial" }
                ]
                testimonials = [
                    { "quote": "Same-day delivery is phenomenal. Ordered my electronics at 9 AM and they arrived before dinner.", "author": "Rachel Green", "role": "Verified Prime Buyer", "company": "Chicago, IL", "avatar_initials": "RG" },
                    { "quote": "Zero hassle returns and unbeatable prices. The best online shopping experience hands down.", "author": "Michael Chang", "role": "Verified Shopper", "company": "Austin, TX", "avatar_initials": "MC" }
                ]
                faq = [
                    { "question": "How fast is same-day delivery?", "answer": "Orders placed before 12:00 PM are delivered directly to your door by 9:00 PM the very same day." },
                    { "question": "What is the return policy?", "answer": "We offer a 30-day no-questions-asked return window with free return labels and instant refunds upon locker drop-off." }
                ]

            # 4. FOOD / RESTAURANT / BISTRO / DINING
            elif has_kw(["food", "restaurant", "restaurants", "dining", "meal", "meals", "chef", "chefs", "gourmet", "kitchen", "bistro", "catering", "burger", "burgers", "pizza", "sushi", "pasta"]):
                brand_name = "L'Artisan Hearth"
                headline = "Culinary Artistry. Farm-to-Table Gastronomy."
                tagline = "Seasonal chef-crafted menus, wood-fired hearth flavors, and handcrafted cocktails in an intimate candlelit setting."
                hero_badge = "🍷 Michelin-Inspired • Farm-Fresh Ingredients"
                primary = "#ea580c"
                secondary = "#fbbf24"
                bg_mode = "dark"
                primary_cta = "Reserve a Table"
                features = [
                    { "title": "Farm-to-Table Organic Harvest", "description": "Directly partnered with local biodynamic growers for vegetables and herbs picked hours before plating.", "icon": "heart" },
                    { "title": "Wood-Fired Hearth Flavors", "description": "Aged white oak embers infuse wild meats and handmade pastas with smoky, nuanced depth.", "icon": "flame" },
                    { "title": "Sommelier Wine Pairings", "description": "Cellar collection of over 400 natural and organic wines curated to elevate every course.", "icon": "award" },
                    { "title": "Intimate Ambient Hospitality", "description": "Warm candlelight, live acoustic jazz, and thoughtful service that makes every dinner a memory.", "icon": "sparkles" }
                ]
                pricing = [
                    { "name": "Prix Fixe 3-Course", "price": "$68", "description": "Appetizer, wood-fired main, and seasonal dessert", "features": ["Choice of Seasonal Starter", "Wood-Fired Signature Entree", "Artisan Dessert Selection"], "highlighted": False, "cta": "Reserve 3-Course" },
                    { "name": "Chef's Tasting Menu", "price": "$125", "description": "7-course gastronomic journey with optional sommelier wine pairing", "features": ["7 Signature Seasonal Courses", "Table-Side Chef Presentation", "Sommelier Wine Pairing Option", "Kitchen Tour & Petit Fours"], "highlighted": True, "cta": "Book Tasting Experience" }
                ]
                testimonials = [
                    { "quote": "The wood-fired sourdough and charred octopus were transcendent. Best dining experience of the year.", "author": "Sophie Martin", "role": "Food Critic", "company": "Michelin Guide Review", "avatar_initials": "SM" }
                ]
                faq = [
                    { "question": "Do you accommodate dietary restrictions and allergies?", "answer": "Yes, our kitchen happily crafts dedicated gluten-free, vegan, and allergen-safe tasting menus with advance notice." }
                ]

            # 5. REAL ESTATE / ARCHITECTURE / LUXURY LIVING
            elif has_kw(["real estate", "property", "properties", "realtor", "realtors", "housing", "villa", "villas", "apartment", "apartments", "condo", "condos", "penthouse", "penthouses", "residence", "residences", "mansion"]):
                brand_name = "Vanguard Estates"
                headline = "Iconic Architecture. Unrivaled Luxury Living."
                tagline = "Discover extraordinary private villas, waterfront estates, and panoramic skyline penthouses in the world's most coveted destinations."
                hero_badge = "🏛️ Prime Waterfront & City Sanctuaries"
                primary = "#0f766e"
                secondary = "#d97706"
                bg_mode = "dark"
                primary_cta = "Explore Portfolio"
                features = [
                    { "title": "Bespoke Architectural Masterpieces", "description": "Custom-designed residences featuring cantilevered glass terraces and organic natural stone.", "icon": "home" },
                    { "title": "Prime Waterfront Locations", "description": "Exclusive coastal and metropolitan addresses with private docks and panoramic vistas.", "icon": "compass" },
                    { "title": "Smart Automation & Security", "description": "Integrated smart home systems, biometric entry, and 24/7 private estate security.", "icon": "shield-check" },
                    { "title": "Private Concierge Services", "description": "White-glove property management, private yacht charters, and lifestyle concierge.", "icon": "award" }
                ]
                pricing = [
                    { "name": "Waterfront Villa", "price": "From $3.2M", "description": "4-bedroom coastal sanctuary with private infinity pool", "features": ["Panoramic Ocean Views", "Private Dock & Beach Access", "Smart Home Automation"], "highlighted": False, "cta": "Schedule Private Tour" },
                    { "name": "Skyline Penthouse", "price": "From $6.8M", "description": "Duplex penthouse with 360-degree metropolitan horizon terrace", "features": ["Private Rooftop Pool", "Direct Elevator Access", "Concierge & Valet Service"], "highlighted": True, "cta": "Inquire with Broker" }
                ]
                testimonials = [
                    { "quote": "The architectural detail, sunset vistas, and seamless transaction exceeded every expectation.", "author": "Arthur Sterling", "role": "Architectural Digest Collector", "company": "Geneva", "avatar_initials": "AS" }
                ]
                faq = [
                    { "question": "Can international buyers acquire properties through Vanguard?", "answer": "Yes, our international legal concierge manages cross-border escrow, residency visas, and tax structuring." }
                ]

            # 6. FASHION / APPAREL / LUXURY STREETWEAR
            elif has_kw(["fashion", "clothing", "apparel", "streetwear", "boutique", "dress", "dresses", "shoes", "style", "wardrobe", "jewelry", "couture", "jacket", "jackets"]):
                brand_name = "Atelier Noir"
                headline = "Timeless Elegance. Sustainable Haute Couture."
                tagline = "Meticulously handcrafted garments sculpted from organic Italian fabrics, blending modern minimalism with effortless silhouette."
                hero_badge = "✨ Sustainable Luxury • Handcrafted in Milan"
                primary = "#18181b"
                secondary = "#e4e4e7"
                bg_mode = "dark"
                primary_cta = "Shop New Capsule"
                features = [
                    { "title": "Handcrafted Organic Silhouettes", "description": "Tailored from regenerative organic silk, virgin wool, and Japanese raw denim.", "icon": "scissors" },
                    { "title": "Limited Edition Micro-Drops", "description": "Small-batch seasonal capsules numbered by hand to ensure timeless uniqueness.", "icon": "sparkles" },
                    { "title": "Zero-Waste Ethical Atelier", "description": "100% fair-wage artisan workshops committed to carbon-neutral production.", "icon": "heart" },
                    { "title": "Complimentary Custom Tailoring", "description": "Personalized sleeve and hem alterations included with every outerwear garment.", "icon": "award" }
                ]
                pricing = [
                    { "name": "Signature Capsule", "price": "From $180", "description": "Core wardrobe essentials crafted from organic cotton and merino wool", "features": ["Organic Fabric Certification", "Complimentary Gift Packaging", "Free Worldwide Express Delivery"], "highlighted": False, "cta": "View Essentials" },
                    { "name": "Atelier Outerwear", "price": "From $450", "description": "Hand-stitched trench coats and tailored double-breasted wool blazers", "features": ["Handmade in Milan Atelier", "Bespoke Monogramming", "Lifetime Fabric Care Warranty"], "highlighted": True, "cta": "Shop Outerwear" }
                ]
                testimonials = [
                    { "quote": "The drape and stitching on the wool overcoat are sublime. A true heirloom piece.", "author": "Clara Dupont", "role": "Vogue Fashion Contributor", "company": "Paris", "avatar_initials": "CD" }
                ]
                faq = [
                    { "question": "How do your sizes run?", "answer": "Our silhouettes offer a relaxed, modern European cut. Consult our detailed 3D fit guide on each product page." }
                ]

            # 7. FITNESS / GYM / WELLNESS / WORKOUT
            elif has_kw(["fitness", "gym", "gyms", "workout", "workouts", "calorie", "calories", "health", "exercise", "muscle", "crossfit", "yoga", "wellness", "cardio", "trainer", "training"]):
                brand_name = "PulseFit Elite"
                headline = "Unleash Your Peak Athletic Performance."
                tagline = "Science-backed high-intensity training, personalized nutrition tracking, and elite coaches to sculpt your strongest body."
                hero_badge = "💪 Science-Backed Coaching • Real Results"
                primary = "#10b981"
                secondary = "#3b82f6"
                bg_mode = "dark"
                primary_cta = "Claim Free Trial Pass"
                features = [
                    { "title": "Science-Backed Workout Logs", "description": "Track sets, volume, and progressive overload with smart visual progression charts.", "icon": "activity" },
                    { "title": "Precision Macro & Calorie Coach", "description": "Instant food photo scanning and personalized daily protein and calorie targets.", "icon": "target" },
                    { "title": "1-on-1 Certified Master Trainers", "description": "Customized strength regimens and recovery protocols built around your lifestyle.", "icon": "award" },
                    { "title": "State-of-the-Art Strength Facility", "description": "Eleiko barbells, recovery cryotherapy, and infrared saunas for complete rejuvenation.", "icon": "zap" }
                ]
                pricing = [
                    { "name": "Basic Gym Access", "price": "$49/mo", "description": "Full access to free weights, machines, and open turf", "features": ["Unlimited Open Gym Hours", "Locker Room & Saunas", "PulseFit Mobile App Access"], "highlighted": False, "cta": "Start Basic Pass" },
                    { "name": "All-Access Coaching", "price": "$99/mo", "description": "Unlimited HIIT classes, nutrition consultation & body scan", "features": ["Unlimited Group HIIT & Yoga", "Monthly Body Composition Scan", "Personalized Calorie Plan", "1 Monthly Trainer Session"], "highlighted": True, "cta": "Join All-Access" }
                ]
                testimonials = [
                    { "quote": "Gained 12 lbs of lean muscle and dropped my 5K time in 3 months. The coaching is unmatched.", "author": "Tyler Brooks", "role": "Marathon Runner", "company": "Denver, CO", "avatar_initials": "TB" }
                ]
                faq = [
                    { "question": "Is PulseFit suitable for complete beginners?", "answer": "Yes! Every member receives a complimentary 1-on-1 foundational movement assessment to build safe habits." }
                ]

            # 8. TRAVEL / RESORTS / VACATION
            elif has_kw(["travel", "hotel", "hotels", "resort", "resorts", "vacation", "vacations", "flight", "flights", "trip", "trips", "adventure", "tourism", "getaway", "island"]):
                brand_name = "Azure Horizon Sanctuaries"
                headline = "Bespoke Luxury Escapes Across the Globe."
                tagline = "Handcrafted journeys, private overwater villas, and unforgettable cultural adventures curated just for you."
                hero_badge = "🌴 Curated 5-Star Sanctuaries Worldwide"
                primary = "#0284c7"
                secondary = "#f59e0b"
                bg_mode = "dark"
                primary_cta = "Plan Your Getaway"
                features = [
                    { "title": "Private Island & Overwater Villas", "description": "Secluded retreats with panoramic turquoise lagoons and private plunge pools.", "icon": "compass" },
                    { "title": "Bespoke Curated Itineraries", "description": "Private yacht excursions, Michelin dining, and insider cultural access.", "icon": "award" },
                    { "title": "All-Inclusive 5-Star Dining", "description": "World-class chefs crafting farm-fresh catches and organic tropical flavors.", "icon": "heart" },
                    { "title": "Dedicated 24/7 Island Concierge", "description": "Your personal butler ensuring every wish is met with effortless grace.", "icon": "sparkles" }
                ]
                pricing = [
                    { "name": "Island Escape (4 Nights)", "price": "$1,450", "description": "Overwater villa, all meals, and speedboat transfers", "features": ["Oceanfront Villa with Plunge Pool", "All Daily Gourmet Dining", "Snorkeling & Kayak Equipment", "Complimentary Spa Treatment"], "highlighted": False, "cta": "Book Escape" },
                    { "name": "Sanctuary Signature (7 Nights)", "price": "$2,890", "description": "Private pool residence with yacht day trip and spa retreat", "features": ["Sunset Water Suite", "Full Day Private Yacht Charter", "Daily Couples Massage", "Private Beach Champagne Dinner"], "highlighted": True, "cta": "Reserve Signature" }
                ]
                testimonials = [
                    { "quote": "The most breathtaking sunset we've ever witnessed. Unrivaled hospitality and serene beauty.", "author": "Liam & Chloe", "role": "Travel Writers", "company": "Wanderlust Magazine", "avatar_initials": "LC" }
                ]
                faq = [
                    { "question": "What is the cancellation policy?", "answer": "We offer full flexibility with 100% refunds up to 14 days prior to your arrival date." }
                ]

            # 9. EDUCATION / ACADEMY / COURSES
            elif has_kw(["education", "course", "courses", "learn", "learning", "academy", "school", "schools", "tutoring", "bootcamp", "skill", "skills", "mentor", "mentors"]):
                brand_name = "SkillCraft Academy"
                headline = "Master In-Demand Skills with World-Class Mentors."
                tagline = "Interactive project-based learning, 1-on-1 industry mentorship, and accredited certifications to accelerate your career."
                hero_badge = "🎓 94% Career Placement Rate • Accredited"
                primary = "#4f46e5"
                secondary = "#06b6d4"
                bg_mode = "dark"
                primary_cta = "Enroll Today"
                features = [
                    { "title": "Hands-On Real-World Projects", "description": "Build production-grade applications and portfolios that hiring managers crave.", "icon": "code" },
                    { "title": "1-on-1 Senior Tech Mentors", "description": "Weekly code reviews and career coaching from engineers at top tech firms.", "icon": "users" },
                    { "title": "Accredited Industry Certification", "description": "Earn recognized credentials that prove mastery to recruiters globally.", "icon": "award" },
                    { "title": "Career Placement Guarantee", "description": "Comprehensive resume polishing, mock interviews, and direct hiring partner referrals.", "icon": "shield-check" }
                ]
                pricing = [
                    { "name": "Self-Paced Core", "price": "$49/mo", "description": "Full access to curriculum, coding exercises, and community", "features": ["120+ Interactive Video Lessons", "Code Sandbox & Quizzes", "Discord Peer Community Access"], "highlighted": False, "cta": "Start Learning" },
                    { "name": "Mentored Bootcamp", "price": "$499", "description": "12-week intensive with 1-on-1 mentor, code reviews, and placement", "features": ["Weekly 1-on-1 Mentor Calls", "3 Portfolio Capstone Projects", "Direct Recruiter Introductions", "Job Placement Support"], "highlighted": True, "cta": "Apply for Bootcamp" }
                ]
                testimonials = [
                    { "quote": "Transitioned from retail to a $95k software engineer role in 4 months. Life-changing program.", "author": "Carlos Gomez", "role": "Full-Stack Engineer", "company": "Vercel Partner", "avatar_initials": "CG" }
                ]
                faq = [
                    { "question": "Are there prerequisites required?", "answer": "No prior experience required! We begin with foundations and progress smoothly to advanced topics." }
                ]

            # 10. UNIVERSAL DYNAMIC SEMANTIC SYNTHESIS FOR ANY TOPIC
            else:
                stop_words = {"the", "a", "an", "and", "or", "for", "with", "to", "in", "of", "on", "at", "by", "page", "landing", "website", "web", "app", "site", "online", "custom", "prompt", "make", "build", "create", "generator", "design", "minimalist"}
                words = [w.capitalize() for w in re.findall(r"\w+", raw_query) if len(w) > 2 and w.lower() not in stop_words]
                
                subject = " ".join(words[:3]) or "Artisan Studio"
                brand_name = "".join(words[:2]) or "AuraCraft"
                if len(brand_name) < 3 or len(brand_name) > 20:
                    brand_name = "ModernCraft"

                headline = f"Discover the Art of {subject}."
                tagline = f"Handcrafted excellence, premium quality, and an unforgettable experience designed for passionate lovers of {raw_query[:40]}."
                hero_badge = f"✨ Handcrafted Excellence • {subject}"
                primary = "#6818cd"
                secondary = "#d4f937"
                bg_mode = "dark"
                primary_cta = f"Explore {brand_name}"
                features = [
                    { "title": f"Artisanal {subject} Craftsmanship", "description": f"Meticulously developed with highest grade materials and dedication to perfection.", "icon": "sparkles" },
                    { "title": "Bespoke Tailored Experience", "description": f"Customized to meet your exact expectations and deliver delight at every touchpoint.", "icon": "heart" },
                    { "title": "Sustainable & Ethical Quality", "description": "Committed to conscious sourcing, transparent practices, and lasting value.", "icon": "shield-check" },
                    { "title": "Dedicated Concierge Support", "description": "Our specialist team is always here to answer questions and ensure 100% satisfaction.", "icon": "award" }
                ]
                pricing = [
                    { "name": "Essential Tier", "price": "$29", "description": f"Standard access to our core {subject} offerings", "features": ["Handcrafted Quality Guarantee", "Complimentary Gift Wrapping", "Standard Nationwide Shipping"], "highlighted": False, "cta": "Get Started" },
                    { "name": "Signature Collection", "price": "$79", "description": f"Full bespoke experience with personalized curation", "features": ["Priority Expedited Shipping", "Limited Edition Curation", "Lifetime Quality Guarantee", "Dedicated Support Specialist"], "highlighted": True, "cta": f"Order {brand_name}" }
                ]
                testimonials = [
                    { "quote": f"The attention to detail and authenticity behind {brand_name} are second to none. Absolutely delightful!", "author": "Elena Rostova", "role": "Verified Collector", "company": "London", "avatar_initials": "ER" }
                ]
                faq = [
                    { "question": f"What makes {brand_name} unique?", "answer": tagline },
                    { "question": "How quickly are orders processed and delivered?", "answer": "All orders are packaged by hand within 24 hours and shipped with priority tracking." }
                ]

            result_intent = {
                "product_name": brand_name,
                "headline": headline,
                "hero_badge": hero_badge,
                "tagline": tagline,
                "target_audience": "Enthusiasts, discerning clients, and active community members",
                "brand_voice": "Minimalist, Warm & Refined" if is_minimalist else "Authentic, Prestigious & Bold",
                "color_palette": { "primary": primary, "secondary": secondary, "accent": "#06b6d4", "bg_mode": bg_mode },
                "core_value_props": [f"Authentic {brand_name} quality", "Handcrafted with passion", "Uncompromising attention to detail"],
                "key_features": features,
                "primary_cta": primary_cta,
                "pricing": pricing,
                "testimonials": testimonials,
                "faq": faq
            }

        # Apply Color Theme Override if selected_theme is specified
        if selected_theme in COLOR_THEMES:
            override_colors = COLOR_THEMES[selected_theme]
            result_intent["color_palette"] = {
                "primary": override_colors["primary"],
                "secondary": override_colors["secondary"],
                "accent": override_colors["primary"],
                "bg_mode": override_colors["bg_mode"]
            }

        return result_intent

    def _build_dynamic_html(self, intent: Dict[str, Any], target_device: str = "desktop") -> str:
        brand = intent.get("product_name", "Modern Studio")
        headline = intent.get("headline", f"Discover the Art of {brand}")
        hero_badge = intent.get("hero_badge", f"✨ Handcrafted Quality • {brand}")
        tagline = intent.get("tagline", "The ultimate experience crafted with passion.")
        primary = intent.get("color_palette", {}).get("primary", "#6818cd")
        secondary = intent.get("color_palette", {}).get("secondary", "#d4f937")
        bg_mode = intent.get("color_palette", {}).get("bg_mode", "dark")
        cta = intent.get("primary_cta", "Explore Offerings")
        features = intent.get("key_features", [])
        pricing = intent.get("pricing", [])
        testimonials = intent.get("testimonials", [])
        faq = intent.get("faq", [])

        bg_color = "#0f172a" if bg_mode == "dark" else "#fcfbf7"
        text_color = "#f8fafc" if bg_mode == "dark" else "#1c1917"
        card_bg = "rgba(30, 41, 59, 0.75)" if bg_mode == "dark" else "rgba(255, 255, 255, 0.9)"
        border_color = "rgba(255, 255, 255, 0.12)" if bg_mode == "dark" else "rgba(0, 0, 0, 0.1)"
        text_muted = "#94a3b8" if bg_mode == "dark" else "#78716c"

        # Viewport tuning
        container_max = "1200px"
        hero_font_size = "3.4rem"
        if target_device == "mobile":
            container_max = "420px"
            hero_font_size = "2.1rem"
        elif target_device == "tablet":
            container_max = "768px"
            hero_font_size = "2.7rem"

        # Build Feature Grid HTML
        feature_cards_html = ""
        for feat in features:
            icon_name = feat.get("icon", "sparkles")
            feature_cards_html += f"""
            <div class="card">
                <div class="card-icon"><i data-lucide="{icon_name}"></i></div>
                <h3>{feat.get('title')}</h3>
                <p>{feat.get('description')}</p>
            </div>"""

        # Build Pricing HTML
        pricing_cards_html = ""
        for p in pricing:
            feat_list = "".join([f'<li><i data-lucide="check" style="color: var(--primary)"></i> {item}</li>' for item in p.get("features", [])])
            featured_cls = " featured" if p.get("highlighted") else ""
            pricing_cards_html += f"""
            <div class="card pricing-card{featured_cls}">
                <h3>{p.get('name')}</h3>
                <p>{p.get('description')}</p>
                <div class="price">{p.get('price')}</div>
                <ul class="pricing-features">
                    {feat_list}
                </ul>
                <a href="#offerings" class="btn btn-primary" style="width: 100%; justify-content: center;">{p.get('cta', cta)}</a>
            </div>"""

        # Build Testimonial HTML
        testimonial_cards_html = ""
        for t in testimonials:
            testimonial_cards_html += f"""
            <div class="card">
                <p style="font-style: italic; font-size: 1.05rem; margin-bottom: 1.2rem; color: var(--text-main);">"{t.get('quote')}"</p>
                <div style="display: flex; align-items: center; gap: 0.8rem;">
                    <div style="width: 40px; height: 40px; border-radius: 50%; background: var(--primary); color: white; display: flex; align-items: center; justify-content: center; font-weight: 700; font-size: 0.85rem;">{t.get('avatar_initials', 'JD')}</div>
                    <div>
                        <div style="font-weight: 700; font-size: 0.95rem;">{t.get('author')}</div>
                        <div style="font-size: 0.8rem; color: var(--text-muted);">{t.get('role')}, {t.get('company')}</div>
                    </div>
                </div>
            </div>"""

        # Build FAQ HTML
        faq_items_html = ""
        for f in faq:
            faq_items_html += f"""
            <div class="faq-item" onclick="this.classList.toggle('active')">
                <h4>{f.get('question')} <i data-lucide="chevron-down"></i></h4>
                <div class="faq-answer">{f.get('answer')}</div>
            </div>"""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{brand} - Official Landing Page</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=Playfair+Display:ital,wght@0,600;1,600&display=swap" rel="stylesheet">
    <script src="https://unpkg.com/lucide@latest"></script>
    <style>
        :root {{
            --primary: {primary};
            --secondary: {secondary};
            --bg-dark: {bg_color};
            --card-bg: {card_bg};
            --border-color: {border_color};
            --text-main: {text_color};
            --text-muted: {text_muted};
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Plus Jakarta Sans', sans-serif; }}
        body {{ background-color: var(--bg-dark); color: var(--text-main); overflow-x: hidden; line-height: 1.6; }}
        
        .container {{ max-width: {container_max}; margin: 0 auto; padding: 0 1.5rem; }}
        .glow {{ position: absolute; border-radius: 50%; filter: blur(140px); opacity: 0.25; z-index: 0; pointer-events: none; }}
        .glow-1 {{ top: -100px; left: 20%; width: 400px; height: 400px; background: var(--primary); }}
        .glow-2 {{ top: 300px; right: 10%; width: 450px; height: 450px; background: var(--secondary); }}
        
        header {{ position: sticky; top: 0; z-index: 100; backdrop-filter: blur(16px); background: rgba(15, 23, 42, 0.75); border-bottom: 1px solid var(--border-color); }}
        .nav-container {{ max-width: {container_max}; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; padding: 1rem 1.5rem; }}
        .logo {{ font-size: 1.4rem; font-weight: 800; color: var(--text-main); display: flex; align-items: center; gap: 0.5rem; }}
        .nav-links {{ display: flex; gap: 1.8rem; list-style: none; }}
        .nav-links a {{ color: var(--text-muted); text-decoration: none; font-weight: 500; font-size: 0.92rem; transition: color 0.3s; }}
        .nav-links a:hover {{ color: var(--text-main); }}
        
        .btn {{ padding: 0.75rem 1.6rem; border-radius: 9999px; font-weight: 600; text-decoration: none; cursor: pointer; transition: all 0.3s ease; display: inline-flex; align-items: center; gap: 0.5rem; font-size: 0.95rem; }}
        .btn-primary {{ background: linear-gradient(135deg, var(--primary), var(--secondary)); color: white; border: none; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25); }}
        .btn-primary:hover {{ transform: translateY(-2px); box-shadow: 0 8px 25px rgba(0, 0, 0, 0.4); }}
        
        .hero {{ max-width: {container_max}; margin: 0 auto; padding: 5.5rem 1.5rem 3.5rem; text-align: center; position: relative; z-index: 1; }}
        .badge {{ display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.45rem 1.3rem; border-radius: 9999px; background: rgba(255, 255, 255, 0.08); border: 1px solid var(--border-color); color: var(--primary); font-size: 0.92rem; font-weight: 600; margin-bottom: 1.5rem; }}
        .hero h1 {{ font-size: {hero_font_size}; font-weight: 800; line-height: 1.15; margin-bottom: 1.4rem; letter-spacing: -0.02em; color: var(--text-main); }}
        .hero p {{ font-size: 1.25rem; color: var(--text-muted); max-width: 780px; margin: 0 auto 2.2rem; line-height: 1.6; }}
        .hero-ctas {{ display: flex; justify-content: center; gap: 1rem; margin-bottom: 2rem; flex-wrap: wrap; }}
        
        .section {{ max-width: {container_max}; margin: 0 auto; padding: 4.5rem 1.5rem; position: relative; z-index: 1; }}
        .section-title {{ text-align: center; margin-bottom: 3.2rem; }}
        .section-title h2 {{ font-size: 2.3rem; font-weight: 800; margin-bottom: 0.7rem; }}
        .section-title p {{ color: var(--text-muted); font-size: 1.1rem; max-width: 650px; margin: 0 auto; }}
        
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1.8rem; }}
        .card {{ background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 1.25rem; padding: 2.2rem; backdrop-filter: blur(12px); transition: all 0.3s ease; }}
        .card:hover {{ transform: translateY(-5px); border-color: var(--primary); }}
        .card-icon {{ width: 50px; height: 50px; border-radius: 14px; background: rgba(255, 255, 255, 0.08); color: var(--primary); display: flex; align-items: center; justify-content: center; margin-bottom: 1.3rem; font-size: 1.4rem; }}
        
        .pricing-card {{ text-align: center; position: relative; }}
        .pricing-card.featured {{ border-color: var(--primary); box-shadow: 0 0 35px rgba(0, 0, 0, 0.25); }}
        .pricing-card .price {{ font-size: 2.6rem; font-weight: 800; margin: 1.2rem 0; color: var(--text-main); }}
        .pricing-features {{ list-style: none; margin: 1.5rem 0 2rem; text-align: left; }}
        .pricing-features li {{ padding: 0.6rem 0; border-bottom: 1px solid var(--border-color); color: var(--text-muted); display: flex; align-items: center; gap: 0.6rem; font-size: 0.95rem; }}
        
        .faq-item {{ background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 1rem; margin-bottom: 1rem; padding: 1.3rem 1.6rem; cursor: pointer; transition: all 0.2s; }}
        .faq-item:hover {{ border-color: var(--primary); }}
        .faq-item h4 {{ display: flex; justify-content: space-between; align-items: center; font-size: 1.1rem; font-weight: 700; }}
        .faq-answer {{ display: none; margin-top: 1rem; color: var(--text-muted); font-size: 0.96rem; line-height: 1.6; }}
        .faq-item.active .faq-answer {{ display: block; }}
        
        footer {{ border-top: 1px solid var(--border-color); padding: 3rem 1.5rem; text-align: center; color: var(--text-muted); font-size: 0.9rem; margin-top: 3rem; }}
    </style>
</head>
<body>
    <div class="glow glow-1"></div>
    <div class="glow glow-2"></div>
    
    <header>
        <div class="nav-container">
            <div class="logo"><i data-lucide="layers" style="color: var(--primary)"></i> {brand}</div>
            <ul class="nav-links">
                <li><a href="#features">Features</a></li>
                <li><a href="#offerings">Offerings</a></li>
                <li><a href="#testimonials">Reviews</a></li>
                <li><a href="#faq">FAQ</a></li>
            </ul>
            <a href="#offerings" class="btn btn-primary">{cta}</a>
        </div>
    </header>

    <section class="hero">
        <div class="badge">{hero_badge}</div>
        <h1>{headline}</h1>
        <p>{tagline}</p>
        <div class="hero-ctas">
            <a href="#offerings" class="btn btn-primary">{cta} <i data-lucide="arrow-right"></i></a>
        </div>
    </section>

    <section id="features" class="section">
        <div class="section-title">
            <h2>Crafted with Uncompromising Quality</h2>
            <p>Every detail engineered with intention, authentic passion, and premium materials.</p>
        </div>
        <div class="grid">
            {feature_cards_html}
        </div>
    </section>

    <section id="testimonials" class="section">
        <div class="section-title">
            <h2>Loved by Connoisseurs & Enthusiasts</h2>
            <p>Read what our community experiences when they choose {brand}.</p>
        </div>
        <div class="grid">
            {testimonial_cards_html}
        </div>
    </section>

    <section id="offerings" class="section">
        <div class="section-title">
            <h2>Curated Selections & Pricing</h2>
            <p>Select the option designed to deliver your ideal experience.</p>
        </div>
        <div class="grid">
            {pricing_cards_html}
        </div>
    </section>

    <section id="faq" class="section">
        <div class="section-title">
            <h2>Frequently Asked Questions</h2>
        </div>
        <div style="max-width: 720px; margin: 0 auto;">
            {faq_items_html}
        </div>
    </section>

    <footer>
        <p>&copy; 2026 {brand}. All rights reserved. Powered by Manijoshi's AI Studio.</p>
    </footer>

    <script>lucide.createIcons();</script>
</body>
</html>"""
