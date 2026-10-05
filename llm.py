import json
import re
import requests
import urllib.parse
from typing import Dict, Any, Optional
from config import Config

class LLMClient:
    def __init__(self, provider: str = None, model: str = None, api_key: str = None):
        self.provider = (provider or Config.DEFAULT_PROVIDER).lower()
        self.model = model or Config.DEFAULT_MODEL
        self.api_key = api_key or Config.get_api_key(self.provider)

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
            print(f"⚠️ API call to {self.provider} failed ({e}). Switching to Smart Query Engine...")
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
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model or 'gemini-1.5-flash'}:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": f"{system_prompt}\n\n{prompt}"}]}
            ]
        }
        res = requests.post(url, json=payload, timeout=60)
        res.raise_for_status()
        data = res.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]

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
        """Smart offline engine that analyzes user queries (single website names or custom prompts) and generates tailored responses."""
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
            brand_name = intent.get("product_name", "Modern Platform")
            tagline = intent.get("tagline", "The ultimate platform experience.")
            features = intent.get("key_features", [])
            pricing = intent.get("pricing", [])
            primary_cta = intent.get("primary_cta", "Get Started")

            return json.dumps({
                "nav": { "brand_name": brand_name, "links": ["Features", "How it Works", "Pricing", "FAQ"], "cta": primary_cta },
                "hero": {
                    "badge": f"✨ Introducing {brand_name}",
                    "headline": f"Experience the Next Era of {brand_name}",
                    "subheadline": tagline,
                    "primary_cta": primary_cta,
                    "secondary_cta": "Watch Product Demo",
                    "trust_metric": f"Trusted by thousands of active users and teams worldwide"
                },
                "features": features,
                "how_it_works": [
                    { "step": "01", "title": f"Create Your {brand_name} Account", "description": f"Sign up in seconds and access your personalized workspace immediately." },
                    { "step": "02", "title": "Configure Your Preferences", "description": "Tailor settings, automated workflows, and integrations to your exact needs." },
                    { "step": "03", "title": "Scale & Collaborate", "description": f"Enjoy seamless performance across mobile, desktop, and cloud devices." }
                ],
                "testimonials": [
                    { "quote": f"{brand_name} transformed our workflow completely. The intuitive interface and speed are unrivaled!", "author": "Sarah Jenkins", "role": "Lead Product Strategist", "company": "Apex Global", "avatar_initials": "SJ" },
                    { "quote": "The design quality, conversion copy, and user experience exceed all expectations.", "author": "Alex Rivera", "role": "Head of Engineering", "company": "TechPulse", "avatar_initials": "AR" }
                ],
                "pricing": pricing,
                "faq": [
                    { "question": f"What is {brand_name}?", "answer": tagline },
                    { "question": f"How do I get started with {brand_name}?", "answer": f"Click '{primary_cta}' to claim your account and unlock instant access." },
                    { "question": "Is this platform responsive across all devices?", "answer": "Yes! The landing page and core application are fully responsive across mobile, tablet, and desktop viewports." }
                ],
                "footer_cta": { "headline": f"Ready to transform your workflow with {brand_name}?", "subheadline": "Join thousands of users scaling their digital operations today.", "button": primary_cta }
            })
        else:
            # Return Product Strategist JSON
            return json.dumps(intent)

    def _analyze_query_intent(self, prompt: str) -> Dict[str, Any]:
        """Parses and analyzes single brand name keywords or detailed custom prompt descriptions."""
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

        # Known Brands Knowledge Dictionary
        KNOWN_BRANDS = {
            "spotify": {
                "product_name": "Spotify",
                "tagline": "Listening is everything. Millions of songs, audiobooks, and podcasts on any device.",
                "target_audience": "Music enthusiasts, podcast listeners, and creators globally",
                "brand_voice": "Vibrant, Iconic, and Energetic",
                "color_palette": { "primary": "#1db954", "secondary": "#191414", "accent": "#1ed760", "bg_mode": "dark" },
                "core_value_props": ["70M+ High Quality Songs", "Personalized Daily Mixes", "Cross-Device Music Hand-off"],
                "key_features": [
                    { "title": "70M+ Ultra HD Songs", "description": "Stream unlimited tracks, albums, and curated playlists without interruptions.", "icon": "music" },
                    { "title": "Personalized Daily Mixes", "description": "AI recommendation engine tailored to your exact listening habits and mood.", "icon": "sparkles" },
                    { "title": "Podcast & Video Shows", "description": "Tune into top global podcasts, video streams, and exclusive original series.", "icon": "radio" },
                    { "title": "Cross-Device Audio Hand-off", "description": "Seamlessly transfer playback across phone, desktop, smart TV, and car audio.", "icon": "smartphone" }
                ],
                "primary_cta": "Get Spotify Free",
                "pricing": [
                    { "name": "Free Tier", "price": "$0/mo", "description": "Shuffle play with ads & standard audio", "features": ["Basic Audio Streaming", "Playlist Creation", "Ad-Supported Playback"], "highlighted": False, "cta": "Get Spotify Free" },
                    { "name": "Premium Individual", "price": "$10.99/mo", "description": "100% ad-free music, offline audio & lossless quality", "features": ["100% Ad-Free Audio", "Offline Downloads", "Unlimited Skips", "High Fidelity Sound"], "highlighted": True, "cta": "Start 1 Month Free" }
                ]
            },
            "netflix": {
                "product_name": "Netflix",
                "tagline": "Watch anywhere. Cancel anytime. Unlimited movies, TV shows, and original series.",
                "target_audience": "Entertainment lovers, families, and binge-watchers",
                "brand_voice": "Cinematic, Bold, and Immersive",
                "color_palette": { "primary": "#e50914", "secondary": "#141414", "accent": "#b81d24", "bg_mode": "dark" },
                "core_value_props": ["Unlimited 4K Content", "Personalized User Profiles", "Offline Downloads"],
                "key_features": [
                    { "title": "Unlimited HD & 4K Streaming", "description": "Watch blockbuster movies, award-winning series, and original documentaries.", "icon": "tv" },
                    { "title": "Personalized AI Profiles", "description": "Smart profile recommendations for every family member and kids area.", "icon": "sparkles" },
                    { "title": "Offline Downloads", "description": "Save your favorite movies and shows to watch on the go without internet.", "icon": "download" },
                    { "title": "Multi-Device Compatibility", "description": "Stream simultaneously on smart TVs, tablets, smartphones, and laptops.", "icon": "monitor" }
                ],
                "primary_cta": "Join Netflix Now",
                "pricing": [
                    { "name": "Standard with Ads", "price": "$6.99/mo", "description": "Great video quality in Full HD", "features": ["Full HD 1080p Resolution", "2 Supported Devices", "Unlimited Movies & Shows"], "highlighted": False, "cta": "Choose Standard" },
                    { "name": "Premium 4K Ultra HD", "price": "$22.99/mo", "description": "4K Ultra HD + Spatial Audio on 4 screens", "features": ["Ultra HD 4K + HDR Video", "4 Concurrent Screens", "Spatial Audio Tech", "6 Download Devices"], "highlighted": True, "cta": "Join Premium" }
                ]
            },
            "airbnb": {
                "product_name": "Airbnb",
                "tagline": "Find unique accommodations, local stays, and unforgettable travel experiences.",
                "target_audience": "Travelers, digital nomads, vacationers, and property hosts",
                "brand_voice": "Welcoming, Adventurous, and Human-Centric",
                "color_palette": { "primary": "#ff385c", "secondary": "#00a699", "accent": "#fc642d", "bg_mode": "light" },
                "core_value_props": ["Unique Stays Worldwide", "Verified Reviews", "AirCover Guest Guarantee"],
                "key_features": [
                    { "title": "Unique Places to Stay", "description": "Discover beachfront villas, cozy cabins, treehouses, and luxury apartments.", "icon": "home" },
                    { "title": "Verified Guest Reviews", "description": "Book with confidence backed by authentic guest ratings and host profiles.", "icon": "shield-check" },
                    { "title": "Local Experiences & Tours", "description": "Participate in local cooking classes, guided hikes, and cultural workshops.", "icon": "map-pin" },
                    { "title": "AirCover Protection", "description": "Comprehensive host and guest protection against cancellations and damages.", "icon": "lock" }
                ],
                "primary_cta": "Explore Stays Near You",
                "pricing": [
                    { "name": "Guest Booking", "price": "Free to Join", "description": "Browse and book millions of stays worldwide", "features": ["Zero Membership Fees", "Instant Booking Confirmation", "AirCover Guest Guarantee"], "highlighted": True, "cta": "Explore Stays" },
                    { "name": "Host Your Space", "price": "3% Host Fee", "description": "Turn your extra space into passive rental income", "features": ["$3M Damage Protection", "Dedicated Host Support", "Smart Dynamic Pricing Tools"], "highlighted": False, "cta": "Become a Host" }
                ]
            },
            "tesla": {
                "product_name": "Tesla",
                "tagline": "Accelerating the world's transition to sustainable energy with electric vehicles and clean solar.",
                "target_audience": "Tech enthusiasts, eco-conscious drivers, and performance automotive lovers",
                "brand_voice": "Futuristic, High-Tech, and Sleek",
                "color_palette": { "primary": "#e82127", "secondary": "#111111", "accent": "#ffffff", "bg_mode": "dark" },
                "core_value_props": ["Full Self-Driving Autopilot", "Instant Torque Acceleration", "50k+ Superchargers"],
                "key_features": [
                    { "title": "Full Self-Driving Autopilot", "description": "Advanced neural network navigation, auto-lane changes, and smart summon capabilities.", "icon": "cpu" },
                    { "title": "Instant Electric Torque", "description": "0 to 60 mph acceleration in as fast as 1.99 seconds with dual-motor AWD.", "icon": "zap" },
                    { "title": "Global Supercharger Access", "description": "Add up to 200 miles of range in just 15 minutes at over 50,000 Superchargers.", "icon": "battery-charging" },
                    { "title": "Over-The-Air Updates", "description": "Continuous software enhancements that add new features and improve range overnight.", "icon": "refresh-cw" }
                ],
                "primary_cta": "Order Custom Tesla",
                "pricing": [
                    { "name": "Model 3 Performance", "price": "$38,990", "description": "Sleek all-electric sedan with 341 mi range", "features": ["341 Miles Estimated Range", "0-60 in 2.9 Seconds", "Autopilot Hardware Included"], "highlighted": True, "cta": "Custom Order" },
                    { "name": "Model Y Long Range", "price": "$44,990", "description": "Versatile utility SUV with maximum cargo space", "features": ["Dual Motor All-Wheel Drive", "7-Seat Seating Option", "76 cu ft Storage Capacity"], "highlighted": False, "cta": "Explore Inventory" }
                ]
            },
            "youtube": {
                "product_name": "YouTube",
                "tagline": "Enjoy the videos and music you love, upload original content, and share it with the world.",
                "target_audience": "Video creators, viewers, and global streaming audiences",
                "brand_voice": "Bold, Creator-Centric, and High-Energy",
                "color_palette": { "primary": "#ff0000", "secondary": "#cc0000", "accent": "#ffffff", "bg_mode": "dark" },
                "core_value_props": ["4K Ultra HD Streaming", "Smart Video Recommendations", "Creator Monetization"],
                "key_features": [
                    { "title": "Ultra HD 4K Video Streaming", "description": "Enjoy zero-latency video playback across billions of creators and channels.", "icon": "play-circle" },
                    { "title": "Smart AI Feed & Recommendations", "description": "Discover personalized recommendations matching your exact interests.", "icon": "sparkles" },
                    { "title": "Creator Studio & Analytics", "description": "Upload content, track subscriber growth, and monetize videos in real time.", "icon": "bar-chart" },
                    { "title": "Live Shorts & Streams", "description": "Engage with live superchats, community polls, and vertical video shorts.", "icon": "video" }
                ],
                "primary_cta": "Explore YouTube Free",
                "pricing": [
                    { "name": "Free Viewer Tier", "price": "$0/mo", "description": "Unlimited access to millions of videos", "features": ["Standard High-Res Streaming", "Community & Channels", "Mobile & Web Access"], "highlighted": False, "cta": "Start Watching" },
                    { "name": "YouTube Premium", "price": "$13.99/mo", "description": "100% ad-free playback, offline downloads, & YouTube Music", "features": ["Ad-Free Video Playback", "Background Play & Downloads", "Included YouTube Music Pro", "High Bitrate 1080p"], "highlighted": True, "cta": "Try 1 Month Free" }
                ]
            }
        }

        result_intent = None

        # Check for known brand match
        for key, data in KNOWN_BRANDS.items():
            if key in clean_query:
                result_intent = json.loads(json.dumps(data))
                break

        if not result_intent:
            # Dynamic Intent Synthesis for Custom Prompt Descriptions
            if any(k in clean_query for k in ["fitness", "gym", "workout", "calorie", "health", "exercise"]):
                brand_name = "FitPulse AI"
                tagline = "Track workouts, count calories, and achieve peak fitness goals with AI coaching."
                audience = "Fitness enthusiasts, athletes, and health-conscious individuals"
                primary = "#10b981"
                secondary = "#3b82f6"
                bg_mode = "dark"
                features = [
                    { "title": "Smart Workout Logging", "description": "Log sets, reps, and cardio exercises effortlessly with automated AI detection.", "icon": "activity" },
                    { "title": "Precision Calorie Counter", "description": "Scan meals or snap food photos for instant breakdown of macros, protein, and calories.", "icon": "target" },
                    { "title": "AI Fitness Coach", "description": "Receive customized daily training plans and recovery insights tailored to your progress.", "icon": "sparkles" },
                    { "title": "Real-Time Progress Telemetry", "description": "Visualize muscle growth, fat loss, and strength gains with intuitive charts.", "icon": "bar-chart-2" }
                ]
            elif any(k in clean_query for k in ["crypto", "bitcoin", "trading", "bot", "blockchain", "solana"]):
                brand_name = "CryptoPulse AI"
                tagline = "Automated crypto trading, real-time market signals, and high-speed execution engine."
                audience = "Crypto traders, Web3 investors, and algorithmic finance professionals"
                primary = "#8b5cf6"
                secondary = "#06b6d4"
                bg_mode = "dark"
                features = [
                    { "title": "Automated Signal Execution", "description": "Execute trades 24/7 with zero-latency exchange webhooks and AI algorithms.", "icon": "zap" },
                    { "title": "AI Sentiment & Volatility Scanner", "description": "Scan thousands of trading pairs in real time to spot profitable breakouts.", "icon": "trending-up" },
                    { "title": "Dynamic Stop-Loss & Risk Shield", "description": "Protect your capital with automated trailing stops and portfolio risk limits.", "icon": "shield-check" },
                    { "title": "Multi-Exchange Portfolio Dashboard", "description": "Unify your Binance, Coinbase, and DEX balances in one real-time dashboard.", "icon": "pie-chart" }
                ]
            elif any(k in clean_query for k in ["portfolio", "resume", "designer", "developer", "showcase"]):
                brand_name = "FolioCraft Studio"
                tagline = "Build stunning, interactive design & developer portfolios in minutes without code."
                audience = "Designers, developers, freelancers, and creative professionals"
                primary = "#6818cd"
                secondary = "#d4f937"
                bg_mode = "dark"
                features = [
                    { "title": "Interactive Layout Canvas", "description": "Drag and drop pixel-perfect visual sections with fluid micro-animations.", "icon": "layout" },
                    { "title": "Custom Domain & Global CDN", "description": "Publish directly to your custom domain backed by sub-second global edge delivery.", "icon": "globe" },
                    { "title": "Client Proofing & Feedback Portal", "description": "Share private password-protected drafts and gather inline client comments.", "icon": "message-square" },
                    { "title": "Visitor Telemetry & Lead Capture", "description": "Know who is viewing your work and capture inbound client leads automatically.", "icon": "users" }
                ]
            elif any(k in clean_query for k in ["food", "restaurant", "dining", "meal", "kitchen"]):
                brand_name = "BiteDash"
                tagline = "Delicious chef-crafted meals delivered hot and fresh from top local restaurants."
                audience = "Food lovers, busy professionals, and families"
                primary = "#f97316"
                secondary = "#eab308"
                bg_mode = "light"
                features = [
                    { "title": "Fast 30-Minute Delivery", "description": "Get your favorite dishes delivered hot and fresh by top-rated local couriers.", "icon": "truck" },
                    { "title": "Curated Local Chef Menus", "description": "Discover hand-crafted gourmet dishes from the highest rated kitchens in your city.", "icon": "award" },
                    { "title": "Real-Time Order GPS Tracking", "description": "Track your meal's preparation and courier's live route on an interactive map.", "icon": "map-pin" },
                    { "title": "Group Ordering & Rewards", "description": "Easily split office lunch orders and earn cashback points on every meal.", "icon": "gift" }
                ]
            else:
                # Fallback dynamic synthesis from query words
                clean_words = [w.capitalize() for w in re.findall(r"\w+", raw_query) if len(w) > 2 and w.lower() not in ["for", "the", "and", "with", "app", "custom", "page", "landing"]]
                inferred = "".join(clean_words[:2]) or "JoStudio"
                if len(inferred) < 3 or len(inferred) > 22:
                    inferred = "ModernStudio"

                brand_name = inferred
                tagline = f"The ultimate next-generation platform for {raw_query[:50]}."
                audience = "Modern teams, creators, and active users"
                primary = "#6818cd"
                secondary = "#d4f937"
                bg_mode = "dark"
                features = [
                    { "title": f"Smart {brand_name} Core", "description": f"Streamline your operations with intelligent {brand_name} capabilities.", "icon": "cpu" },
                    { "title": "Automated Workflows", "description": "Connect your tools and trigger real-time AI routines seamlessly.", "icon": "sparkles" },
                    { "title": "Enterprise Security", "description": "Bank-grade data encryption, granular access control, and privacy protection.", "icon": "shield" },
                    { "title": "Real-Time Telemetry", "description": "Gain total visibility with instant analytics and operational telemetry.", "icon": "bar-chart" }
                ]

            result_intent = {
                "product_name": brand_name,
                "tagline": tagline,
                "target_audience": audience,
                "brand_voice": "Bold, High-Performance, and Modern",
                "color_palette": { "primary": primary, "secondary": secondary, "accent": "#06b6d4", "bg_mode": bg_mode },
                "core_value_props": [
                    f"Seamless {brand_name} user experience",
                    "Enterprise reliability and lightning speed",
                    "Real-time analytics and telemetry insights"
                ],
                "key_features": features,
                "primary_cta": f"Get Started with {brand_name}",
                "pricing": [
                    { "name": "Free Tier", "price": "$0/mo", "description": "Essential access for creators & viewers", "features": ["Standard Platform Access", "Core Integrations", "Community Support"], "highlighted": False, "cta": "Start Free" },
                    { "name": "Pro Plan", "price": "$19/mo", "description": "Full power suite for active users & teams", "features": ["Unlimited Workflows", "Priority 24/7 Support", "Custom Branding", "Real-Time Telemetry"], "highlighted": True, "cta": f"Get {brand_name} Pro" }
                ]
            }

        # Apply Color Theme Override to ALL intents (including known brands) if selected_theme is specified
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
        tagline = intent.get("tagline", "The ultimate platform experience.")
        primary = intent.get("color_palette", {}).get("primary", "#6818cd")
        secondary = intent.get("color_palette", {}).get("secondary", "#d4f937")
        bg_mode = intent.get("color_palette", {}).get("bg_mode", "dark")
        cta = intent.get("primary_cta", "Get Started")
        features = intent.get("key_features", [])
        pricing = intent.get("pricing", [])

        bg_color = "#0f172a" if bg_mode == "dark" else "#f8fafc"
        text_color = "#f8fafc" if bg_mode == "dark" else "#0f172a"
        card_bg = "rgba(30, 41, 59, 0.75)" if bg_mode == "dark" else "rgba(255, 255, 255, 0.85)"
        border_color = "rgba(255, 255, 255, 0.12)" if bg_mode == "dark" else "rgba(0, 0, 0, 0.12)"
        text_muted = "#94a3b8" if bg_mode == "dark" else "#64748b"

        # Viewport tuning
        container_max = "1200px"
        hero_font_size = "3.5rem"
        if target_device == "mobile":
            container_max = "420px"
            hero_font_size = "2.2rem"
        elif target_device == "tablet":
            container_max = "768px"
            hero_font_size = "2.8rem"

        # Build Feature Grid HTML
        feature_cards_html = ""
        for feat in features:
            icon_name = feat.get("icon", "zap")
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
                <a href="#" class="btn btn-primary" style="width: 100%; justify-content: center;">{p.get('cta', cta)}</a>
            </div>"""

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{brand} - Official Landing Page</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
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
        * {{ margin: 0; padding: 0; box-sizing: border-box; font-family: 'Outfit', sans-serif; }}
        body {{ background-color: var(--bg-dark); color: var(--text-main); overflow-x: hidden; line-height: 1.6; }}
        
        .container {{ max-width: {container_max}; margin: 0 auto; padding: 0 1.5rem; }}
        .glow {{ position: absolute; border-radius: 50%; filter: blur(120px); opacity: 0.35; z-index: 0; pointer-events: none; }}
        .glow-1 {{ top: -100px; left: 20%; width: 400px; height: 400px; background: var(--primary); }}
        .glow-2 {{ top: 300px; right: 10%; width: 450px; height: 450px; background: var(--secondary); }}
        
        header {{ position: sticky; top: 0; z-index: 100; backdrop-filter: blur(16px); background: rgba(15, 23, 42, 0.85); border-bottom: 1px solid var(--border-color); }}
        .nav-container {{ max-width: {container_max}; margin: 0 auto; display: flex; justify-content: space-between; align-items: center; padding: 1.1rem 1.5rem; }}
        .logo {{ font-size: 1.5rem; font-weight: 800; background: linear-gradient(135deg, var(--primary), var(--secondary)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; display: flex; align-items: center; gap: 0.5rem; }}
        .nav-links {{ display: flex; gap: 1.8rem; list-style: none; }}
        .nav-links a {{ color: var(--text-muted); text-decoration: none; font-weight: 500; transition: color 0.3s; }}
        .nav-links a:hover {{ color: var(--text-main); }}
        
        .btn {{ padding: 0.75rem 1.6rem; border-radius: 9999px; font-weight: 600; text-decoration: none; cursor: pointer; transition: all 0.3s ease; display: inline-flex; align-items: center; gap: 0.5rem; }}
        .btn-primary {{ background: linear-gradient(135deg, var(--primary), var(--secondary)); color: white; border: none; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25); }}
        .btn-primary:hover {{ transform: translateY(-2px); box-shadow: 0 8px 25px rgba(0, 0, 0, 0.4); }}
        
        .hero {{ max-width: {container_max}; margin: 0 auto; padding: 5rem 1.5rem 3.5rem; text-align: center; position: relative; z-index: 1; }}
        .badge {{ display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.4rem 1.2rem; border-radius: 9999px; background: rgba(255, 255, 255, 0.08); border: 1px solid var(--border-color); color: var(--primary); font-size: 0.9rem; font-weight: 600; margin-bottom: 1.5rem; }}
        .hero h1 {{ font-size: {hero_font_size}; font-weight: 800; line-height: 1.15; margin-bottom: 1.4rem; background: linear-gradient(180deg, #ffffff, var(--text-muted)); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        .hero p {{ font-size: 1.2rem; color: var(--text-muted); max-width: 750px; margin: 0 auto 2.2rem; }}
        .hero-ctas {{ display: flex; justify-content: center; gap: 1rem; margin-bottom: 2rem; flex-wrap: wrap; }}
        
        .section {{ max-width: {container_max}; margin: 0 auto; padding: 4rem 1.5rem; position: relative; z-index: 1; }}
        .section-title {{ text-align: center; margin-bottom: 3rem; }}
        .section-title h2 {{ font-size: 2.3rem; font-weight: 800; margin-bottom: 0.7rem; }}
        .section-title p {{ color: var(--text-muted); font-size: 1.1rem; }}
        
        .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 1.8rem; }}
        .card {{ background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 1.25rem; padding: 2rem; backdrop-filter: blur(12px); transition: all 0.3s ease; }}
        .card:hover {{ transform: translateY(-5px); border-color: var(--primary); }}
        .card-icon {{ width: 48px; height: 48px; border-radius: 12px; background: rgba(255, 255, 255, 0.08); color: var(--primary); display: flex; align-items: center; justify-content: center; margin-bottom: 1.2rem; font-size: 1.4rem; }}
        
        .pricing-card {{ text-align: center; position: relative; }}
        .pricing-card.featured {{ border-color: var(--primary); box-shadow: 0 0 30px rgba(0, 0, 0, 0.3); }}
        .pricing-card .price {{ font-size: 2.8rem; font-weight: 800; margin: 1.2rem 0; color: white; }}
        .pricing-features {{ list-style: none; margin: 1.5rem 0 2rem; text-align: left; }}
        .pricing-features li {{ padding: 0.6rem 0; border-bottom: 1px solid var(--border-color); color: var(--text-muted); display: flex; align-items: center; gap: 0.6rem; }}
        
        .faq-item {{ background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 1rem; margin-bottom: 1rem; padding: 1.2rem 1.5rem; cursor: pointer; }}
        .faq-item h4 {{ display: flex; justify-content: space-between; align-items: center; font-size: 1.1rem; font-weight: 700; }}
        .faq-answer {{ display: none; margin-top: 1rem; color: var(--text-muted); font-size: 0.95rem; }}
        .faq-item.active .faq-answer {{ display: block; }}
        
        footer {{ border-top: 1px solid var(--border-color); padding: 3rem 1.5rem; text-align: center; color: var(--text-muted); font-size: 0.9rem; margin-top: 3rem; }}
    </style>
</head>
<body>
    <div class="glow glow-1"></div>
    <div class="glow glow-2"></div>
    
    <header>
        <div class="nav-container">
            <div class="logo"><i data-lucide="layers"></i> {brand}</div>
            <ul class="nav-links">
                <li><a href="#features">Features</a></li>
                <li><a href="#pricing">Pricing</a></li>
                <li><a href="#faq">FAQ</a></li>
            </ul>
            <a href="#pricing" class="btn btn-primary">{cta}</a>
        </div>
    </header>

    <section class="hero">
        <div class="badge"><i data-lucide="sparkles"></i> Official {brand} Experience</div>
        <h1>Next Generation {brand}</h1>
        <p>{tagline}</p>
        <div class="hero-ctas">
            <a href="#pricing" class="btn btn-primary">{cta} <i data-lucide="arrow-right"></i></a>
        </div>
    </section>

    <section id="features" class="section">
        <div class="section-title">
            <h2>Why Millions Choose {brand}</h2>
            <p>Built for speed, intelligent automation, and high-performance delivery</p>
        </div>
        <div class="grid">
            {feature_cards_html}
        </div>
    </section>

    <section id="pricing" class="section">
        <div class="section-title">
            <h2>Transparent Pricing Plans</h2>
            <p>Pick the ideal tier for your growth</p>
        </div>
        <div class="grid">
            {pricing_cards_html}
        </div>
    </section>

    <section id="faq" class="section">
        <div class="section-title">
            <h2>Frequently Asked Questions</h2>
        </div>
        <div style="max-width: 700px; margin: 0 auto;">
            <div class="faq-item" onclick="this.classList.toggle('active')">
                <h4>What makes {brand} unique? <i data-lucide="chevron-down"></i></h4>
                <div class="faq-answer">{tagline}</div>
            </div>
            <div class="faq-item" onclick="this.classList.toggle('active')">
                <h4>How do I activate my account? <i data-lucide="chevron-down"></i></h4>
                <div class="faq-answer">Simply select a plan above and click '{cta}' to get started immediately.</div>
            </div>
            <div class="faq-item" onclick="this.classList.toggle('active')">
                <h4>Is this platform responsive across viewports? <i data-lucide="chevron-down"></i></h4>
                <div class="faq-answer">Yes! The page and interface are optimized for {target_device.upper()} viewports and all modern mobile devices.</div>
            </div>
        </div>
    </section>

    <footer>
        <p>&copy; 2026 {brand} Official Platform. Powered by Jo's AI Studio.</p>
    </footer>

    <script>lucide.createIcons();</script>
</body>
</html>"""
