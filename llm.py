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
        """Parses and analyzes prompt keywords across 20+ specialized industries and synthesizes tailored concepts."""
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
        is_minimalist = has_kw(["minimalist", "minimalism", "minimal", "clean", "simple", "zen", "scandinavian", "japandi"])

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

        # SEMANTIC DOMAIN ONTOLOGY (Priority Ordered from Highly-Specific to Broad)
        if not result_intent:
            # 1. GAMING / ESPORTS / GAME ENGINE / FPS / BATTLE ROYALE
            if has_kw(["game", "gaming", "gamer", "esports", "streamer", "twitch", "rpg", "arcade", "fps", "playstation", "xbox", "nintendo", "steam", "vr", "gameplay", "battle royale", "unreal engine", "unreal", "unity engine"]):
                brand_name = "Nexus Realm Studios"
                headline = "Next-Gen Unreal 5 Gaming Worlds."
                tagline = "Immerse yourself in hyper-realistic open-world combat, ray-traced spatial acoustics, and cross-platform esports championships."
                hero_badge = "🎮 120 FPS Ray-Tracing • Cross-Play Multiplayer"
                primary = "#8b5cf6"
                secondary = "#06b6d4"
                bg_mode = "dark"
                primary_cta = "Join Free Beta Access"
                features = [
                    { "title": "Unreal Engine 5 Nanite Realism", "description": "Photorealistic volumetric lighting, dynamic destructible environments, and 4K textures.", "icon": "tv" },
                    { "title": "Tick-Rate 128 Dedicated Servers", "description": "Ultra-low latency multiplayer with zero lag and proprietary AI anti-cheat security.", "icon": "zap" },
                    { "title": "Cross-Play on PC, Console & VR", "description": "Team up with your squad across Steam, PlayStation 5, Xbox Series X, and VR headsets.", "icon": "monitor" },
                    { "title": "Player-Driven Creator Economy", "description": "Build custom maps, trade cosmetic skins, and host private tournament lobbies.", "icon": "sparkles" }
                ]
                pricing = [
                    { "name": "Standard Edition", "price": "Free to Play", "description": "Full access to core battle royale, ranked arenas & matchmaking", "features": ["Ranked Competitive Matchmaking", "Base Weapon Arsenal", "Weekly Community Tournaments"], "highlighted": False, "cta": "Download Game" },
                    { "name": "Founder Battle Pass", "price": "$19.99/season", "description": "100+ exclusive mythic weapon skins, character outfits & double XP", "features": ["Mythic Founder Weapon Skin", "100 Tier Progression Rewards", "Double XP Season Booster", "VIP Discord Tournament Pass"], "highlighted": True, "cta": "Get Founder Pass" }
                ]
                testimonials = [
                    { "quote": "The gunplay feel and spatial audio are insane. Hands down the most addictive multiplayer shooter of 2026.", "author": "Alex Rivera", "role": "Esports Content Creator", "company": "Twitch Partner", "avatar_initials": "AR" }
                ]
                faq = [
                    { "question": "What are the minimum PC hardware requirements?", "answer": "Runs smooth 60 FPS on GTX 1660 / Ryzen 5 or higher; 120 FPS+ with RTX 40-series." }
                ]

            # 2. PETS / DOGS / CATS / VETERINARY / PET FOOD / GROOMING
            elif has_kw(["pet", "pets", "dog", "dogs", "cat", "cats", "puppy", "kitten", "vet", "veterinary", "animal", "grooming", "pet food", "dog food", "cat food"]):
                brand_name = "Paws & Whiskers Sanctuary"
                headline = "Pure Love & Nutrition for Your Best Friend."
                tagline = "Veterinarian-formulated organic meals, gentle fear-free grooming, and 24/7 veterinary wellness for healthy, joyful pets."
                hero_badge = "🐾 100% Organic Ingredients • Vet Approved"
                primary = "#10b981"
                secondary = "#f59e0b"
                bg_mode = "dark"
                primary_cta = "Explore Pet Nutrition"
                features = [
                    { "title": "Human-Grade Fresh Organic Food", "description": "Gently cooked whole meats, organic veggies, and essential omega-3s with zero fillers.", "icon": "heart" },
                    { "title": "Fear-Free Gentle Grooming", "description": "Stress-free hydrotherapy baths, soothing blueberry facials, and breed-specific styling.", "icon": "sparkles" },
                    { "title": "24/7 On-Demand Vet Telehealth", "description": "Instant video consultations with licensed veterinarians whenever questions arise.", "icon": "shield-check" },
                    { "title": "Personalized Puppy & Senior Care", "description": "Nutritional plans tailored by breed size, weight, and life stage for boundless energy.", "icon": "award" }
                ]
                pricing = [
                    { "name": "Monthly Fresh Food Box", "price": "$39/mo", "description": "Personalized fresh meal portions delivered frozen to your door", "features": ["Pre-Portioned Fresh Meals", "Free Thermal Shipping", "Freeze-Dried Organic Treats Included"], "highlighted": True, "cta": "Start Pet Plan" },
                    { "name": "Spa Grooming Day", "price": "$65", "description": "Full bath, deshedding brush, nail trim, and organic ear clean", "features": ["Hypoallergenic Oatmeal Shampoo", "Full Blowout & Deshedding", "Teeth Brushing & Paw Balm"], "highlighted": False, "cta": "Book Spa Session" }
                ]
                testimonials = [
                    { "quote": "My golden retriever's coat is gleaming and his digestion issues completely vanished in two weeks!", "author": "Jessica Taylor", "role": "Pet Parent", "company": "Seattle, WA", "avatar_initials": "JT" }
                ]
                faq = [
                    { "question": "How do you calculate the exact meal portion?", "answer": "Our smart algorithm calculates exact daily calories based on your dog's weight, activity level, and breed." }
                ]

            # 3. LEGAL / LAW FIRM / ATTORNEY / LITIGATION / PATENTS
            elif has_kw(["law", "legal", "lawyer", "lawyers", "attorney", "attorneys", "litigation", "counsel", "court", "corporate law", "patent", "patents", "trademark", "trademarks", "intellectual property", "law firm"]):
                brand_name = "Vanguard Legal Counsel"
                headline = "Strategic Defense. Uncompromising Advocacy."
                tagline = "Elite trial attorneys and corporate counsel defending your rights, protecting intellectual property, and closing high-stakes transactions."
                hero_badge = "⚖️ $500M+ Won for Clients • Top 100 Trial Lawyers"
                primary = "#1e293b"
                secondary = "#d97706"
                bg_mode = "dark"
                primary_cta = "Request Confidential Case Review"
                features = [
                    { "title": "Master Trial Strategists", "description": "Over 25 years of courtroom experience in high-stakes corporate and civil litigation.", "icon": "shield-check" },
                    { "title": "Intellectual Property & Patents", "description": "Safeguard your innovations with global trademark registrations and patent defense.", "icon": "award" },
                    { "title": "M&A and Cross-Border Contracts", "description": "Bespoke transaction structuring, regulatory compliance, and due diligence.", "icon": "code" },
                    { "title": "100% Confidential Client Privilege", "description": "Every consultation is protected by strict attorney-client privilege from day one.", "icon": "heart" }
                ]
                pricing = [
                    { "name": "Initial Case Assessment", "price": "Free", "description": "30-minute confidential consultation with a senior partner", "features": ["Comprehensive Case Merit Review", "Litigation Roadmap & Strategy", "Clear Fee Structure Quote"], "highlighted": False, "cta": "Book Free Review" },
                    { "name": "Corporate Retainer", "price": "Custom", "description": "Full-spectrum outside general counsel for growing enterprises", "features": ["Dedicated Partner Lead", "Contract Drafting & Negotiation", "Regulatory Compliance Audits", "Priority 24/7 Response Time"], "highlighted": True, "cta": "Inquire Retainer" }
                ]
                testimonials = [
                    { "quote": "Their negotiation strategy saved our company millions during acquisition. Decisive, razor-sharp counsel.", "author": "Robert Evans", "role": "CEO", "company": "Aura Tech Global", "avatar_initials": "RE" }
                ]
                faq = [
                    { "question": "How quickly can you take on an urgent case?", "answer": "Our rapid-response litigation team is available within 24 hours to file motions or issue injunctions." }
                ]

            # 4. CRYPTO / WEB3 / FINTECH / BANKING / TRADING
            elif has_kw(["crypto", "cryptocurrency", "bitcoin", "ethereum", "web3", "fintech", "banking", "finance", "investment", "trading", "wallet", "defi", "blockchain", "payments", "stocks"]):
                brand_name = "Aetherium Finance"
                headline = "Institutional-Grade Web3 & Multi-Asset Wealth."
                tagline = "Trade global crypto assets, earn automated high-yield staking, and manage digital liquidity with institutional multi-sig security."
                hero_badge = "⚡ 0.0% Maker Fees • $2.5B+ Protected Liquidity"
                primary = "#06b6d4"
                secondary = "#6366f1"
                bg_mode = "dark"
                primary_cta = "Open Secure Account"
                features = [
                    { "title": "Sub-Millisecond Order Execution", "description": "High-frequency matching engine with deep aggregated global liquidity books.", "icon": "zap" },
                    { "title": "SOC-2 Type II Certified Cold Vaults", "description": "Institutional MPC multi-signature custody insured up to $250M per wallet.", "icon": "shield-check" },
                    { "title": "Automated High-Yield Staking", "description": "Earn up to 8.2% APY compound yield automatically deposited into your account daily.", "icon": "activity" },
                    { "title": "Universal Cross-Chain Bridge", "description": "Swap tokens instantly across 14 EVM and Solana chains with zero slippage.", "icon": "refresh-cw" }
                ]
                pricing = [
                    { "name": "Standard Trader", "price": "0.1% Fee", "description": "Full access to spot trading, fiat on-ramps & mobile app", "features": ["Over 350+ Crypto Pairs", "Instant Bank ACH Transfers", "Hardware Key 2FA Support"], "highlighted": False, "cta": "Start Trading" },
                    { "name": "Institutional VIP", "price": "0.02% Fee", "description": "Dedicated OTC desk, FIX API connectivity & sub-accounts", "features": ["Dedicated OTC Broker", "Institutional API Limits", "Zero Staking Unbonding Lock", "24/7 Private Telemetry Desk"], "highlighted": True, "cta": "Apply for VIP" }
                ]
                testimonials = [
                    { "quote": "Fastest order execution and lowest slippage in the DeFi space. The custody security gives complete peace of mind.", "author": "Julian Vance", "role": "Hedge Fund Principal", "company": "Vertex Capital", "avatar_initials": "JV" }
                ]
                faq = [
                    { "question": "How are client funds protected?", "answer": "100% of user assets are backed 1:1 in cold storage vaults with real-time Merkle-Tree Proof of Reserves." }
                ]

            # 5. HEALTHCARE / MEDICAL / CLINIC / DENTAL / DOCTOR
            elif has_kw(["medical", "clinic", "hospital", "doctor", "dentist", "dental", "therapy", "therapist", "pharmacy", "medicine", "mental health", "healthcare"]):
                brand_name = "Apex Medical & Longevity"
                headline = "Compassionate Care. Precision Medical Science."
                tagline = "Comprehensive preventative care, board-certified physician specialists, and advanced diagnostic imaging tailored to your health."
                hero_badge = "🩺 Board-Certified Physicians • Same-Day Appointments"
                primary = "#0284c7"
                secondary = "#10b981"
                bg_mode = "dark"
                primary_cta = "Book Doctor Consultation"
                features = [
                    { "title": "Board-Certified Medical Specialists", "description": "Multidisciplinary team of physicians and surgeons with top hospital affiliations.", "icon": "award" },
                    { "title": "Same-Day Diagnostic Imaging & Labs", "description": "In-house 3T MRI, digital ultrasound, and instant lab biomarkers for rapid results.", "icon": "activity" },
                    { "title": "Personalized Preventative Longevity", "description": "Comprehensive biological age analysis, nutritional genetic mapping, and preventive care.", "icon": "heart" },
                    { "title": "24/7 Telehealth Video Access", "description": "Connect with an on-call physician from the comfort of home in minutes.", "icon": "smartphone" }
                ]
                pricing = [
                    { "name": "General Wellness Visit", "price": "$95", "description": "Complete physical exam, vitals check, and prescription renewals", "features": ["Comprehensive Vitals Exam", "Digital Health Records Access", "Same-Day Prescription Routing"], "highlighted": False, "cta": "Schedule Visit" },
                    { "name": "Annual Longevity Concierge", "price": "$850/yr", "description": "Unlimited physician visits, full diagnostic biomarker panel & 24/7 direct doctor line", "features": ["Unlimited In-Person & Telehealth", "Complete 120-Biomarker Panel", "Annual Full-Body MRI Scan", "Direct Doctor WhatsApp Line"], "highlighted": True, "cta": "Join Concierge" }
                ]
                testimonials = [
                    { "quote": "Dr. Vance caught an early health marker that changed my life. Thorough, caring, and truly state-of-the-art.", "author": "David Miller", "role": "Patient", "company": "New York", "avatar_initials": "DM" }
                ]
                faq = [
                    { "question": "Do you accept standard health insurance?", "answer": "Yes, we partner with all major PPO insurance networks and provide itemized superbills for out-of-network reimbursement." }
                ]

            # 6. BEAUTY / SKINCARE / COSMETICS / SERUM
            elif has_kw(["beauty", "skincare", "skin", "cosmetics", "makeup", "massage", "hair", "dermatology", "serum", "aesthetic", "glow ritual", "gua sha"]):
                brand_name = "Lumière Botanical Beauty"
                headline = "Radiant Glow. Bio-Active Botanical Skincare."
                tagline = "Clinically proven clinical botanicals, hyaluronic peptides, and pure essential oils designed to restore luminous youthful skin."
                hero_badge = "🌸 100% Clean Vegan • Dermatologist Approved"
                primary = "#ec4899"
                secondary = "#fbcfe8"
                bg_mode = "dark"
                primary_cta = "Discover Glow Ritual"
                features = [
                    { "title": "Bio-Fermented Vitamin C & Peptides", "description": "Target fine lines and brighten dark spots with multi-molecular weight hydration.", "icon": "sparkles" },
                    { "title": "Zero Parabens, Sulfates or Fragrance", "description": "100% cruelty-free, vegan certified formulations safe for the most sensitive skin.", "icon": "heart" },
                    { "title": "Cold-Pressed Seed Oils", "description": "Rich in antioxidant squalane and rosehip oil to lock in lasting moisture barrier.", "icon": "award" },
                    { "title": "Sustainable Glass Packaging", "description": "Refillable UV-blocking violet glass bottles that preserve active nutrient potency.", "icon": "shield-check" }
                ]
                pricing = [
                    { "name": "Daily Glow Essentials", "price": "$64", "description": "Cleanser, hydrating botanical toner, and antioxidant serum", "features": ["Gentle Amino Acid Cleanser", "Hydrating Rosewater Mist", "Vitamin C Radiance Serum"], "highlighted": False, "cta": "Shop Essentials" },
                    { "name": "Youth Renewal Collection", "price": "$128", "description": "Complete 5-step regimen with retinol night elixir and peptide eye cream", "features": ["Full 5-Piece Regimen", "Bakuchiol Overnight Repair Elixir", "Rose Quartz Sculpting Gua Sha", "Silk Travel Toiletry Case"], "highlighted": True, "cta": "Order Collection" }
                ]
                testimonials = [
                    { "quote": "My complexion has never looked this plump and radiant. My makeup goes on flawlessly now.", "author": "Camille Monet", "role": "Beauty Editor", "company": "Elle Magazine", "avatar_initials": "CM" }
                ]
                faq = [
                    { "question": "Is this suitable for acne-prone or sensitive skin?", "answer": "Yes, all our products are non-comedogenic, fragrance-free, and clinically allergy tested." }
                ]

            # 7. INTERIOR DESIGN / SCANDINAVIAN FURNITURE / HOME DECOR
            elif has_kw(["furniture", "interior", "interiors", "decor", "home decor", "sofa", "sofas", "chair", "table", "scandinavian furniture", "living room", "furnishings", "woodwork"]):
                brand_name = "Nordic Timber Studio" if is_minimalist else "Haven & Hearth Interiors"
                headline = "Organic Minimalism. Handcrafted Solid Oak Living."
                tagline = "Timeless Scandinavian furniture sculpted from sustainable Nordic hardwoods, creating calm, functional, and soulful living spaces."
                hero_badge = "🪵 Sustainable FSC Oak • Lifetime Craft Warranty"
                primary = "#44403c"
                secondary = "#d6d3d1"
                bg_mode = "dark" if not is_minimalist else "light"
                primary_cta = "View Furniture Catalog"
                features = [
                    { "title": "FSC-Certified Solid European Oak", "description": "Sustainably harvested timber air-dried and finished with natural beeswax and organic oils.", "icon": "home" },
                    { "title": "Traditional Mortise & Tenon Joinery", "description": "Built by generational woodworkers without synthetic adhesives for heirloom durability.", "icon": "scissors" },
                    { "title": "Ergonomic Sculptural Silhouettes", "description": "Harmonious organic curves designed to support natural posture with clean negative space.", "icon": "sparkles" },
                    { "title": "Complimentary White-Glove Room Delivery", "description": "Assembled directly inside your home with all packaging materials sustainably recycled.", "icon": "truck" }
                ]
                pricing = [
                    { "name": "Minimalist Dining Chair", "price": "From $240", "description": "Solid curved oak chair with breathable woven paper cord seat", "features": ["Solid European White Oak", "Handwoven Paper Cord Seat", "Natural Matt Oil Finish"], "highlighted": False, "cta": "Order Chair" },
                    { "name": "Stockholm Sectional Sofa", "price": "From $1,890", "description": "Deep feather-down modular sofa in Belgian linen or bouclé", "features": ["Solid Hardwood Internal Frame", "Belgian Linen Removable Slipcovers", "Feather-Down Cushion Core", "Free In-Home White Glove Delivery"], "highlighted": True, "cta": "Configure Sofa" }
                ]
                testimonials = [
                    { "quote": "The dining table is a masterpiece of woodworking. Our home immediately felt calmer and more grounded.", "author": "Henrik Lindqvist", "role": "Architect", "company": "Copenhagen", "avatar_initials": "HL" }
                ]
                faq = [
                    { "question": "Can I order fabric and wood finish swatches?", "answer": "Yes! We mail complimentary swatch boxes containing all 12 fabric textures and 4 solid wood finishes." }
                ]

            # 8. CYBERSECURITY / CLOUD / SAAS / DEVOPS / AI TOOLS
            elif has_kw(["saas", "software", "cloud", "devops", "security", "cybersecurity", "analytics", "api", "developer", "backend", "platform", "ai tool", "ai editor", "workflow", "automation", "ci/cd", "telemetry"]):
                brand_name = "CloudMatrix AI"
                headline = "Supercharge Your Cloud & AI Engineering Workflow."
                tagline = "Automate continuous deployments, monitor real-time telemetry, and scale distributed cloud applications with zero infrastructure headaches."
                hero_badge = "⚡ 99.999% SLA • Real-Time Edge Telemetry"
                primary = "#6366f1"
                secondary = "#a855f7"
                bg_mode = "dark"
                primary_cta = "Start 14-Day Free Trial"
                features = [
                    { "title": "Automated Edge CI/CD Pipelines", "description": "Deploy global serverless functions and containers to 300+ edge locations in seconds.", "icon": "zap" },
                    { "title": "Zero-Trust Infrastructure Security", "description": "Automatic mTLS encryption, fine-grained RBAC permissions, and automated vulnerability scanning.", "icon": "shield-check" },
                    { "title": "Real-Time Distributed Telemetry", "description": "Deep distributed tracing, memory profiling, and instant error alerts before users notice.", "icon": "activity" },
                    { "title": "SDKs for Python, Node, Go & Rust", "description": "Integrate with 3 lines of code using lightweight, type-safe open source libraries.", "icon": "code" }
                ]
                pricing = [
                    { "name": "Developer Hobby", "price": "$0/mo", "description": "Perfect for personal projects and early prototypes", "features": ["Up to 3 Active Projects", "100K Edge API Requests", "Community Discord Support"], "highlighted": False, "cta": "Start Free" },
                    { "name": "Pro Team", "price": "$49/mo", "description": "For growing engineering teams requiring high throughput and SLAs", "features": ["Unlimited Edge Projects", "10M Edge API Requests", "SOC-2 Type II Compliance", "Priority 24/7 Slack Support"], "highlighted": True, "cta": "Start Pro Trial" }
                ]
                testimonials = [
                    { "quote": "Cut our monthly infrastructure bill by 40% and reduced deploy times from 15 minutes to 20 seconds.", "author": "Sarah Chen", "role": "VP of Engineering", "company": "HyperScale Corp", "avatar_initials": "SC" }
                ]
                faq = [
                    { "question": "Can I self-host or deploy in a private VPC?", "answer": "Yes, our enterprise tier supports air-gapped on-premise deployments and private AWS/GCP/Azure VPC peering." }
                ]

            # 9. TRAVEL / RESORTS / VACATION
            elif has_kw(["travel", "hotel", "hotels", "resort", "resorts", "vacation", "vacations", "flight", "flights", "trip", "trips", "adventure", "tourism", "getaway", "island", "cruise", "safari"]):
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

            # 10. EDUCATION / ACADEMY / COURSES / BOOTCAMP
            elif has_kw(["education", "course", "courses", "learn", "learning", "academy", "school", "schools", "tutoring", "bootcamp", "skill", "skills", "mentor", "mentors", "university", "class", "classes"]):
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

            # 11. COFFEE / CAFE / ROASTERY / BAKERY
            elif has_kw(["coffee", "cafe", "espresso", "latte", "cappuccino", "roast", "roastery", "brew", "brews", "beans", "barista", "bakery", "mocha", "tea", "matcha", "croissant", "pastry", "pastries"]):
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
                    { "quote": "The most peaceful coffee sanctuary in town. The Ethiopian pour-over is floral, sweet, and unforgettable.", "author": "Maya Lin", "role": "Food & Architecture Critic", "company": "Metropolitan Living", "avatar_initials": "ML" }
                ]
                faq = [
                    { "question": "Where are your coffee beans sourced?", "answer": "We source 100% directly from smallholder organic farms with fair-trade price transparency, ensuring living wages for growers." }
                ]

            # 12. CARS / AUTOMOTIVE / SUPERCARS / RACING
            elif has_kw(["car", "cars", "automobile", "automobiles", "vehicle", "vehicles", "supercar", "supercars", "sports car", "hypercar", "horsepower", "racing", "motor", "motors", "ev", "driving", "torque", "exhaust", "bmw", "porsche", "ferrari", "lamborghini", "tesla"]):
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
                    { "question": "What is the 0-60 acceleration and top speed?", "answer": "The Apex GT accelerates from 0-60 mph in 2.5 seconds with launch control and reaches an electronically governed top speed of 215 mph." }
                ]

            # 13. REAL ESTATE / ARCHITECTURE / LUXURY ESTATES
            elif has_kw(["real estate", "realtor", "realtors", "housing", "villa", "villas", "apartment", "apartments", "condo", "condos", "penthouse", "penthouses", "residence", "residences", "mansion", "mansions", "waterfront"]):
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

            # 14. FASHION / APPAREL / LUXURY STREETWEAR / JEWELRY / WATCHES
            elif has_kw(["fashion", "clothing", "apparel", "streetwear", "boutique", "dress", "dresses", "shoes", "style", "wardrobe", "jewelry", "couture", "jacket", "jackets", "watch", "watches", "diamond", "gold", "silver", "silk"]):
                brand_name = "Atelier Noir"
                headline = "Timeless Elegance. Sustainable Haute Couture."
                tagline = "Meticulously handcrafted garments and fine jewelry sculpted from organic materials, blending modern minimalism with effortless silhouette."
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

            # 15. FITNESS / GYM / WELLNESS / WORKOUT
            elif has_kw(["fitness", "gym", "gyms", "workout", "workouts", "calorie", "calories", "exercise", "muscle", "crossfit", "yoga", "wellness", "cardio", "trainer", "training", "pilates"]):
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

            # 16. FOOD / RESTAURANT / BISTRO / DINING / BURGER / PIZZA
            elif has_kw(["food", "restaurant", "restaurants", "dining", "meal", "meals", "chef", "chefs", "gourmet", "kitchen", "bistro", "catering", "burger", "burgers", "pizza", "sushi", "pasta", "tacos", "barbecue", "bbq", "steakhouse", "ramen"]):
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

            # 17. AMAZON / E-COMMERCE / MARKETPLACE / RETAIL
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
                    { "question": "How fast is same-day delivery?", "answer": "Orders placed before 12:00 PM are delivered directly to your door by 9:00 PM the very same day." }
                ]

            # 18. UNIVERSAL DYNAMIC SEMANTIC SYNTHESIS FOR ANY CUSTOM WORDS/TOPICS
            else:
                stop_words = {"the", "a", "an", "and", "or", "for", "with", "to", "in", "of", "on", "at", "by", "page", "landing", "website", "web", "app", "site", "online", "custom", "prompt", "make", "build", "create", "generator", "design", "minimalist", "please", "i", "want"}
                words = [w for w in re.findall(r"\w+", raw_query) if len(w) > 2 and w.lower() not in stop_words]
                
                subject_words = [w.capitalize() for w in words[:3]]
                subject = " ".join(subject_words) or "Modern Craft"
                brand_name = "".join([w.capitalize() for w in words[:2]]) or "AuraCraft"
                if len(brand_name) < 3 or len(brand_name) > 20:
                    brand_name = f"{subject_words[0]}Studio" if subject_words else "ModernStudio"

                headline = f"Discover the Art of {subject}."
                clean_desc = re.sub(r"(?i)^(landing page for|website for|create a page about|build a|generate a)\s*", "", raw_query).strip()
                tagline = f"Handcrafted excellence, premium quality, and an unforgettable experience designed for passionate lovers of {clean_desc or subject}."
                hero_badge = f"✨ Handcrafted Excellence • {subject}"
                primary = "#6818cd"
                secondary = "#d4f937"
                bg_mode = "dark"
                primary_cta = f"Explore {subject}"
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
        how_it_works = intent.get("how_it_works", [
            {"step": "01", "title": "Discover & Explore", "description": "Browse our curated collection and find exactly what you're looking for."},
            {"step": "02", "title": "Personalize Your Experience", "description": "Customize your selection to match your exact preferences and needs."},
            {"step": "03", "title": "Enjoy the Difference", "description": "Experience exceptional quality and craftsmanship delivered to you."}
        ])

        bg_color = "#0b0f1a" if bg_mode == "dark" else "#f9f8f5"
        text_color = "#f1f5f9" if bg_mode == "dark" else "#1a1a2e"
        card_bg = "rgba(255,255,255,0.05)" if bg_mode == "dark" else "rgba(255,255,255,0.92)"
        card_bg_hover = "rgba(255,255,255,0.09)" if bg_mode == "dark" else "rgba(255,255,255,1)"
        border_color = "rgba(255,255,255,0.1)" if bg_mode == "dark" else "rgba(0,0,0,0.08)"
        text_muted = "#94a3b8" if bg_mode == "dark" else "#64748b"
        nav_bg = "rgba(11,15,26,0.85)" if bg_mode == "dark" else "rgba(249,248,245,0.90)"
        section_alt = "rgba(255,255,255,0.025)" if bg_mode == "dark" else "rgba(0,0,0,0.025)"

        container_max = "1200px"
        hero_font_size = "3.8rem"
        hero_font_mobile = "2.2rem"
        if target_device == "mobile":
            container_max = "480px"
            hero_font_size = "2.2rem"
            hero_font_mobile = "2.0rem"
        elif target_device == "tablet":
            container_max = "820px"
            hero_font_size = "2.9rem"
            hero_font_mobile = "2.2rem"

        icons_map = {
            "sparkles": "✦", "coffee": "☕", "heart": "♥", "award": "★", "flame": "🔥",
            "gauge": "⚡", "shield-check": "🛡", "disc": "💿", "activity": "📈", "target": "🎯",
            "truck": "🚚", "refresh-cw": "🔄", "code": "💻", "users": "👥", "compass": "🧭",
            "home": "🏡", "scissors": "✂", "music": "🎵", "radio": "📻", "smartphone": "📱",
            "download": "⬇", "monitor": "🖥", "tv": "📺", "zap": "⚡"
        }

        feature_cards_html = ""
        for feat in features:
            icon_char = icons_map.get(feat.get("icon", "sparkles"), "✦")
            feature_cards_html += f"""
            <div class="feature-card reveal">
                <div class="feature-icon">{icon_char}</div>
                <h3>{feat.get('title', '')}</h3>
                <p>{feat.get('description', '')}</p>
            </div>"""

        hiw_html = ""
        for step in how_it_works:
            hiw_html += f"""
            <div class="hiw-step">
                <div class="hiw-number">{step.get('step', '01')}</div>
                <div class="hiw-content">
                    <h3>{step.get('title', '')}</h3>
                    <p>{step.get('description', '')}</p>
                </div>
            </div>"""

        pricing_cards_html = ""
        for p in pricing:
            feat_list = "".join([f'<li><span class="check-icon">✓</span> {item}</li>' for item in p.get("features", [])])
            featured_cls = " featured" if p.get("highlighted") else ""
            popular_badge = '<div class="popular-badge">Most Popular</div>' if p.get("highlighted") else ""
            btn_cls = "btn-primary" if p.get("highlighted") else "btn-outline"
            pricing_cards_html += f"""
            <div class="pricing-card{featured_cls} reveal">
                {popular_badge}
                <div class="pricing-header">
                    <h3>{p.get('name', '')}</h3>
                    <p class="pricing-desc">{p.get('description', '')}</p>
                    <div class="price-amount">{p.get('price', '')}</div>
                </div>
                <ul class="pricing-features">{feat_list}</ul>
                <a href="#contact" class="btn {btn_cls}">{p.get('cta', cta)}</a>
            </div>"""

        testimonial_cards_html = ""
        for t in testimonials:
            initials = t.get("avatar_initials", "JD")
            testimonial_cards_html += f"""
            <div class="testimonial-card reveal">
                <span class="stars">★★★★★</span>
                <p class="quote">"{t.get('quote', '')}"</p>
                <div class="author-row">
                    <div class="avatar">{initials}</div>
                    <div class="author-info">
                        <div class="author-name">{t.get('author', '')}</div>
                        <div class="author-role">{t.get('role', '')}, {t.get('company', '')}</div>
                    </div>
                </div>
            </div>"""

        faq_items_html = ""
        for i, f in enumerate(faq):
            faq_items_html += f"""
            <div class="faq-item">
                <button class="faq-q" onclick="toggleFaq({i})">
                    <span>{f.get('question', '')}</span>
                    <span class="faq-arrow" id="arrow-{i}">▾</span>
                </button>
                <div class="faq-a" id="faqans-{i}">{f.get('answer', '')}</div>
            </div>"""

        stats = intent.get("stats", [
            {"value": "10K+", "label": "Happy Customers"},
            {"value": "4.9★", "label": "Average Rating"},
            {"value": "99%", "label": "Satisfaction Rate"},
            {"value": "24/7", "label": "Support Available"},
        ])
        stats_html = "".join([
            f'<div class="stat-item"><div class="stat-value">{s["value"]}</div><div class="stat-label">{s["label"]}</div></div>'
            for s in stats
        ])

        footer_cta = intent.get("footer_cta", {
            "headline": f"Ready to experience {brand}?",
            "subheadline": "Join thousands of satisfied customers today.",
            "button": cta
        })

        # Build gradient hero headline
        if "." in headline:
            parts = headline.split(".", 1)
            hero_h1 = f'<span class="gradient-text">{parts[0]}.</span>{parts[1]}'
        else:
            hero_h1 = f'<span class="gradient-text">{headline}</span>'

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{brand} — Official Landing Page</title>
    <meta name="description" content="{tagline}">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
    <style>
        :root {{
            --primary: {primary};
            --secondary: {secondary};
            --bg: {bg_color};
            --card-bg: {card_bg};
            --card-hover: {card_bg_hover};
            --border: {border_color};
            --text: {text_color};
            --muted: {text_muted};
            --nav-bg: {nav_bg};
            --alt-bg: {section_alt};
            --radius: 1.2rem;
            --radius-sm: 0.75rem;
        }}
        *, *::before, *::after {{ margin:0; padding:0; box-sizing:border-box; }}
        html {{ scroll-behavior: smooth; }}
        body {{ background: var(--bg); color: var(--text); font-family: 'Outfit', sans-serif; overflow-x: hidden; line-height: 1.65; }}
        .blobs {{ position:fixed; top:0; left:0; width:100%; height:100%; z-index:0; pointer-events:none; overflow:hidden; }}
        .blob {{ position:absolute; border-radius:50%; filter:blur(130px); opacity:0.15; animation:blobFloat 20s ease-in-out infinite alternate; }}
        .b1 {{ width:600px; height:600px; background:var(--primary); top:-200px; left:-100px; }}
        .b2 {{ width:500px; height:500px; background:var(--secondary); top:25%; right:-100px; animation-delay:-8s; }}
        .b3 {{ width:380px; height:380px; background:var(--primary); bottom:-80px; left:30%; animation-delay:-15s; }}
        @keyframes blobFloat {{ 0%{{transform:translate(0,0) scale(1)}} 100%{{transform:translate(45px,35px) scale(1.1)}} }}
        .container {{ max-width:{container_max}; margin:0 auto; padding:0 1.5rem; position:relative; z-index:1; }}
        nav {{ position:sticky; top:0; z-index:1000; background:var(--nav-bg); backdrop-filter:blur(20px) saturate(180%); -webkit-backdrop-filter:blur(20px); border-bottom:1px solid var(--border); transition:box-shadow 0.3s; }}
        .nav-in {{ max-width:{container_max}; margin:0 auto; display:flex; align-items:center; justify-content:space-between; padding:1rem 1.5rem; }}
        .logo {{ font-size:1.35rem; font-weight:800; background:linear-gradient(135deg,var(--primary),var(--secondary)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; text-decoration:none; letter-spacing:-0.02em; }}
        .nav-links {{ display:flex; gap:2rem; list-style:none; }}
        .nav-links a {{ color:var(--muted); text-decoration:none; font-weight:500; font-size:0.95rem; transition:color 0.25s; }}
        .nav-links a:hover {{ color:var(--text); }}
        .hamburger {{ display:none; flex-direction:column; gap:5px; cursor:pointer; background:none; border:none; padding:4px; }}
        .hamburger span {{ display:block; width:24px; height:2px; background:var(--text); border-radius:2px; }}
        .mob-menu {{ display:none; flex-direction:column; background:var(--nav-bg); border-top:1px solid var(--border); padding:1rem 1.5rem; position:relative; z-index:999; }}
        .mob-menu a {{ color:var(--text); text-decoration:none; font-size:1rem; font-weight:500; padding:0.75rem 0; border-bottom:1px solid var(--border); display:block; }}
        .mob-menu.open {{ display:flex; }}
        .btn {{ display:inline-flex; align-items:center; gap:0.4rem; padding:0.7rem 1.7rem; border-radius:9999px; font-weight:600; font-size:0.95rem; font-family:'Outfit',sans-serif; text-decoration:none; cursor:pointer; border:none; transition:all 0.3s cubic-bezier(0.34,1.56,0.64,1); letter-spacing:0.01em; }}
        .btn-primary {{ background:linear-gradient(135deg,var(--primary) 0%,var(--secondary) 100%); color:#fff; box-shadow:0 6px 24px rgba(0,0,0,0.25); }}
        .btn-primary:hover {{ transform:translateY(-3px) scale(1.03); box-shadow:0 12px 32px rgba(0,0,0,0.35); }}
        .btn-outline {{ background:transparent; color:var(--text); border:1.5px solid var(--border); }}
        .btn-outline:hover {{ background:var(--card-hover); border-color:var(--primary); transform:translateY(-2px); }}
        .btn-ghost {{ background:rgba(255,255,255,0.06); color:var(--text); border:1px solid var(--border); }}
        .btn-ghost:hover {{ background:rgba(255,255,255,0.1); transform:translateY(-2px); }}
        .hero {{ padding:6rem 1.5rem 4rem; text-align:center; max-width:{container_max}; margin:0 auto; position:relative; z-index:1; }}
        .badge {{ display:inline-flex; align-items:center; gap:0.5rem; padding:0.4rem 1.2rem; border-radius:9999px; background:rgba(255,255,255,0.07); border:1px solid var(--border); color:var(--primary); font-size:0.88rem; font-weight:600; margin-bottom:1.8rem; letter-spacing:0.02em; animation:fadeDown 0.6s ease both; }}
        .hero h1 {{ font-size:clamp({hero_font_mobile},5vw,{hero_font_size}); font-weight:900; line-height:1.1; letter-spacing:-0.03em; margin-bottom:1.4rem; animation:fadeUp 0.7s 0.1s ease both; }}
        .gradient-text {{ background:linear-gradient(135deg,var(--primary),var(--secondary)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }}
        .hero-sub {{ font-size:clamp(1rem,2.5vw,1.2rem); color:var(--muted); max-width:680px; margin:0 auto 2.5rem; line-height:1.7; animation:fadeUp 0.7s 0.2s ease both; }}
        .hero-ctas {{ display:flex; gap:1rem; justify-content:center; flex-wrap:wrap; animation:fadeUp 0.7s 0.3s ease both; }}
        .hero-trust {{ margin-top:2rem; font-size:0.85rem; color:var(--muted); animation:fadeUp 0.7s 0.4s ease both; }}
        .stats-bar {{ background:var(--card-bg); border:1px solid var(--border); border-radius:var(--radius); backdrop-filter:blur(12px); display:flex; flex-wrap:wrap; overflow:hidden; max-width:{container_max}; margin:3rem auto 0; position:relative; z-index:1; }}
        .stat-item {{ flex:1; min-width:140px; text-align:center; padding:1.8rem 1rem; border-right:1px solid var(--border); transition:background 0.3s; }}
        .stat-item:last-child {{ border-right:none; }}
        .stat-item:hover {{ background:var(--card-hover); }}
        .stat-value {{ font-size:2rem; font-weight:800; letter-spacing:-0.02em; background:linear-gradient(135deg,var(--primary),var(--secondary)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; }}
        .stat-label {{ font-size:0.83rem; color:var(--muted); margin-top:0.2rem; font-weight:500; }}
        section {{ padding:5rem 1.5rem; position:relative; z-index:1; }}
        section.altbg {{ background:var(--alt-bg); }}
        .sec-label {{ display:inline-block; font-size:0.75rem; font-weight:700; letter-spacing:0.13em; text-transform:uppercase; color:var(--primary); margin-bottom:0.75rem; }}
        .sec-head {{ text-align:center; margin-bottom:3.5rem; }}
        .sec-head h2 {{ font-size:clamp(1.8rem,4vw,2.6rem); font-weight:800; letter-spacing:-0.025em; margin-bottom:0.75rem; line-height:1.2; }}
        .sec-head p {{ color:var(--muted); font-size:1.05rem; max-width:580px; margin:0 auto; }}
        .feat-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(250px,1fr)); gap:1.5rem; max-width:{container_max}; margin:0 auto; }}
        .feat-card {{ background:var(--card-bg); border:1px solid var(--border); border-radius:var(--radius); padding:2rem; backdrop-filter:blur(12px); transition:all 0.35s cubic-bezier(0.34,1.56,0.64,1); position:relative; overflow:hidden; }}
        .feat-card::before {{ content:''; position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg,var(--primary),var(--secondary)); opacity:0; transition:opacity 0.3s; }}
        .feat-card:hover {{ transform:translateY(-8px); border-color:var(--primary); background:var(--card-hover); box-shadow:0 20px 60px rgba(0,0,0,0.2); }}
        .feat-card:hover::before {{ opacity:1; }}
        .feat-icon {{ width:54px; height:54px; border-radius:14px; border:1px solid var(--border); background:rgba(255,255,255,0.06); display:flex; align-items:center; justify-content:center; font-size:1.5rem; margin-bottom:1.3rem; }}
        .feat-card h3 {{ font-size:1.05rem; font-weight:700; margin-bottom:0.55rem; }}
        .feat-card p {{ font-size:0.91rem; color:var(--muted); line-height:1.65; }}
        .hiw-grid {{ display:flex; flex-direction:column; max-width:720px; margin:0 auto; }}
        .hiw-step {{ display:flex; gap:2rem; align-items:flex-start; padding:2rem 0; border-bottom:1px solid var(--border); }}
        .hiw-step:last-child {{ border-bottom:none; }}
        .hiw-step:hover .hiw-num {{ transform:scale(1.1); }}
        .hiw-num {{ flex-shrink:0; width:56px; height:56px; border-radius:50%; background:linear-gradient(135deg,var(--primary),var(--secondary)); color:#fff; font-size:1.05rem; font-weight:800; display:flex; align-items:center; justify-content:center; box-shadow:0 8px 24px rgba(0,0,0,0.2); transition:transform 0.3s cubic-bezier(0.34,1.56,0.64,1); }}
        .hiw-text h3 {{ font-size:1.1rem; font-weight:700; margin-bottom:0.4rem; }}
        .hiw-text p {{ color:var(--muted); font-size:0.93rem; line-height:1.65; }}
        .test-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(280px,1fr)); gap:1.5rem; max-width:{container_max}; margin:0 auto; }}
        .test-card {{ background:var(--card-bg); border:1px solid var(--border); border-radius:var(--radius); padding:2rem; backdrop-filter:blur(12px); transition:all 0.3s; }}
        .test-card:hover {{ transform:translateY(-4px); border-color:var(--primary); box-shadow:0 16px 48px rgba(0,0,0,0.18); }}
        .stars {{ color:#f59e0b; font-size:0.9rem; letter-spacing:2px; margin-bottom:1rem; display:block; }}
        .quote {{ font-size:0.96rem; line-height:1.7; font-style:italic; margin-bottom:1.5rem; }}
        .auth-row {{ display:flex; align-items:center; gap:0.85rem; }}
        .avatar {{ width:44px; height:44px; border-radius:50%; background:linear-gradient(135deg,var(--primary),var(--secondary)); color:#fff; font-weight:700; font-size:0.85rem; display:flex; align-items:center; justify-content:center; flex-shrink:0; }}
        .auth-name {{ font-weight:700; font-size:0.93rem; }}
        .auth-role {{ font-size:0.79rem; color:var(--muted); }}
        .price-grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(270px,1fr)); gap:1.5rem; max-width:{container_max}; margin:0 auto; align-items:start; }}
        .price-card {{ background:var(--card-bg); border:1px solid var(--border); border-radius:var(--radius); padding:2.2rem; backdrop-filter:blur(12px); position:relative; transition:all 0.3s; }}
        .price-card.featured {{ border-color:var(--primary); box-shadow:0 0 0 1px var(--primary), 0 24px 64px rgba(0,0,0,0.25); transform:scale(1.03); }}
        .price-card:hover:not(.featured) {{ transform:translateY(-4px); border-color:var(--primary); }}
        .pop-badge {{ position:absolute; top:-13px; left:50%; transform:translateX(-50%); background:linear-gradient(135deg,var(--primary),var(--secondary)); color:#fff; font-size:0.73rem; font-weight:700; padding:0.28rem 1rem; border-radius:9999px; white-space:nowrap; letter-spacing:0.05em; }}
        .price-name {{ font-size:1.15rem; font-weight:700; margin-bottom:0.4rem; }}
        .price-desc {{ color:var(--muted); font-size:0.88rem; margin-bottom:1.1rem; }}
        .price-amt {{ font-size:2.4rem; font-weight:900; letter-spacing:-0.04em; background:linear-gradient(135deg,var(--primary),var(--secondary)); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; margin-bottom:1.5rem; }}
        .price-feats {{ list-style:none; margin-bottom:1.8rem; display:flex; flex-direction:column; gap:0.55rem; }}
        .price-feats li {{ display:flex; align-items:center; gap:0.6rem; font-size:0.88rem; color:var(--muted); padding-bottom:0.55rem; border-bottom:1px solid var(--border); }}
        .price-feats li:last-child {{ border-bottom:none; }}
        .chk {{ color:var(--primary); font-weight:700; font-size:0.85rem; flex-shrink:0; }}
        .price-card .btn {{ width:100%; justify-content:center; margin-top:auto; }}
        .faq-wrap {{ max-width:760px; margin:0 auto; display:flex; flex-direction:column; gap:0.75rem; }}
        .faq-item {{ background:var(--card-bg); border:1px solid var(--border); border-radius:var(--radius-sm); overflow:hidden; transition:border-color 0.25s; }}
        .faq-item:hover {{ border-color:var(--primary); }}
        .faq-q {{ width:100%; display:flex; justify-content:space-between; align-items:center; padding:1.2rem 1.5rem; background:none; border:none; cursor:pointer; color:var(--text); font-size:1rem; font-weight:600; font-family:'Outfit',sans-serif; text-align:left; gap:1rem; }}
        .faq-arrow {{ font-size:1.2rem; color:var(--primary); transition:transform 0.3s; flex-shrink:0; }}
        .faq-arrow.open {{ transform:rotate(180deg); }}
        .faq-a {{ display:none; padding:0 1.5rem 1.2rem; color:var(--muted); font-size:0.94rem; line-height:1.7; border-top:1px solid var(--border); }}
        .faq-a.open {{ display:block; }}
        .fcta-wrap {{ padding:5rem 1.5rem; position:relative; z-index:1; }}
        .fcta-inner {{ max-width:{container_max}; margin:0 auto; background:linear-gradient(135deg,var(--primary) 0%,var(--secondary) 100%); border-radius:2rem; padding:4rem 3rem; text-align:center; position:relative; overflow:hidden; }}
        .fcta-inner::before {{ content:''; position:absolute; top:-50%; left:-50%; width:200%; height:200%; background:radial-gradient(circle,rgba(255,255,255,0.15) 0%,transparent 60%); animation:spin 22s linear infinite; }}
        @keyframes spin {{ from{{transform:rotate(0deg)}} to{{transform:rotate(360deg)}} }}
        .fcta-inner h2 {{ font-size:clamp(1.8rem,4vw,2.8rem); font-weight:900; color:#fff; margin-bottom:0.8rem; letter-spacing:-0.025em; position:relative; }}
        .fcta-inner p {{ color:rgba(255,255,255,0.85); font-size:1.05rem; margin-bottom:2rem; position:relative; }}
        .fcta-inner .btn {{ background:#fff; color:var(--primary); font-weight:700; box-shadow:0 8px 32px rgba(0,0,0,0.2); position:relative; }}
        .fcta-inner .btn:hover {{ transform:translateY(-3px) scale(1.04); }}
        footer {{ border-top:1px solid var(--border); padding:2rem 1.5rem; text-align:center; color:var(--muted); font-size:0.88rem; position:relative; z-index:1; }}
        footer a {{ color:var(--primary); text-decoration:none; }}
        @keyframes fadeDown {{ from{{opacity:0;transform:translateY(-20px)}} to{{opacity:1;transform:translateY(0)}} }}
        @keyframes fadeUp {{ from{{opacity:0;transform:translateY(24px)}} to{{opacity:1;transform:translateY(0)}} }}
        .reveal {{ opacity:0; transform:translateY(30px); transition:opacity 0.65s ease,transform 0.65s ease; }}
        .reveal.visible {{ opacity:1; transform:translateY(0); }}
        @media (max-width:768px) {{
            .nav-links,.nav-cta {{ display:none; }}
            .hamburger {{ display:flex; }}
            .hero {{ padding:3.5rem 1.25rem 2.5rem; }}
            .hero-ctas {{ flex-direction:column; align-items:center; }}
            .stat-item {{ min-width:110px; padding:1.2rem 0.5rem; }}
            .stat-value {{ font-size:1.4rem; }}
            .hiw-step {{ gap:1.25rem; }}
            .hiw-num {{ width:44px; height:44px; font-size:0.88rem; }}
            .price-card.featured {{ transform:scale(1); }}
            .fcta-inner {{ padding:2.5rem 1.5rem; border-radius:1.25rem; }}
            section {{ padding:3.5rem 1.25rem; }}
        }}
    </style>
</head>
<body>
<div class="blobs"><div class="blob b1"></div><div class="blob b2"></div><div class="blob b3"></div></div>
<nav id="topnav">
    <div class="nav-in">
        <a href="#" class="logo">{brand}</a>
        <ul class="nav-links">
            <li><a href="#features">Features</a></li>
            <li><a href="#process">Process</a></li>
            <li><a href="#pricing">Pricing</a></li>
            <li><a href="#reviews">Reviews</a></li>
            <li><a href="#faq">FAQ</a></li>
        </ul>
        <a href="#pricing" class="btn btn-primary nav-cta">{cta}</a>
        <button class="hamburger" onclick="toggleMob()" aria-label="Menu"><span></span><span></span><span></span></button>
    </div>
    <div class="mob-menu" id="mobMenu">
        <a href="#features" onclick="toggleMob()">Features</a>
        <a href="#process" onclick="toggleMob()">Process</a>
        <a href="#pricing" onclick="toggleMob()">Pricing</a>
        <a href="#reviews" onclick="toggleMob()">Reviews</a>
        <a href="#faq" onclick="toggleMob()">FAQ</a>
        <a href="#pricing" class="btn btn-primary" style="margin-top:1rem;justify-content:center;" onclick="toggleMob()">{cta}</a>
    </div>
</nav>
<section class="hero">
    <div class="badge">{hero_badge}</div>
    <h1>{hero_h1}</h1>
    <p class="hero-sub">{tagline}</p>
    <div class="hero-ctas">
        <a href="#pricing" class="btn btn-primary">{cta} →</a>
        <a href="#features" class="btn btn-ghost">Learn More</a>
    </div>
    <p class="hero-trust">✓ No commitment  •  ✓ Instant access  •  ✓ Cancel anytime</p>
</section>
<div style="padding:0 1.5rem;position:relative;z-index:1;max-width:{container_max};margin:0 auto;">
    <div class="stats-bar reveal">{stats_html}</div>
</div>
<section id="features" class="altbg">
    <div class="container">
        <div class="sec-head reveal">
            <span class="sec-label">Why Choose Us</span>
            <h2>Everything You Need, Nothing You Don’t</h2>
            <p>Thoughtfully crafted features that deliver real, tangible results.</p>
        </div>
        <div class="feat-grid">{feature_cards_html}</div>
    </div>
</section>
<section id="process">
    <div class="container">
        <div class="sec-head reveal">
            <span class="sec-label">The Process</span>
            <h2>How It Works</h2>
            <p>Three simple steps to get started and experience the difference.</p>
        </div>
        <div class="hiw-grid reveal">{hiw_html}</div>
    </div>
</section>
<section id="reviews" class="altbg">
    <div class="container">
        <div class="sec-head reveal">
            <span class="sec-label">Social Proof</span>
            <h2>Loved by Thousands Worldwide</h2>
            <p>Real experiences from our passionate community of customers.</p>
        </div>
        <div class="test-grid">{testimonial_cards_html}</div>
    </div>
</section>
<section id="pricing">
    <div class="container">
        <div class="sec-head reveal">
            <span class="sec-label">Pricing</span>
            <h2>Simple, Transparent Pricing</h2>
            <p>Choose the plan that fits your needs. No hidden fees, ever.</p>
        </div>
        <div class="price-grid">{pricing_cards_html}</div>
    </div>
</section>
<section id="faq" class="altbg">
    <div class="container">
        <div class="sec-head reveal">
            <span class="sec-label">FAQ</span>
            <h2>Frequently Asked Questions</h2>
            <p>Everything you need to know, answered clearly.</p>
        </div>
        <div class="faq-wrap reveal">{faq_items_html}</div>
    </div>
</section>
<div class="fcta-wrap reveal">
    <div class="fcta-inner">
        <h2>{footer_cta.get('headline', f'Ready to experience {brand}?')}</h2>
        <p>{footer_cta.get('subheadline', 'Join thousands of satisfied customers today.')}</p>
        <a href="#pricing" class="btn">{footer_cta.get('button', cta)} →</a>
    </div>
</div>
<footer>
    <p>© 2026 <strong>{brand}</strong>. All rights reserved. Powered by <a href="#">Manijoshi's AI Studio</a>.</p>
</footer>
<script>
    function toggleMob(){{document.getElementById('mobMenu').classList.toggle('open');}}
    function toggleFaq(i){{
        var a=document.getElementById('faqans-'+i), r=document.getElementById('arrow-'+i), o=a.classList.contains('open');
        document.querySelectorAll('.faq-a').forEach(function(e){{e.classList.remove('open');}});
        document.querySelectorAll('.faq-arrow').forEach(function(e){{e.classList.remove('open');}});
        if(!o){{a.classList.add('open');r.classList.add('open');}}
    }}
    var io=new IntersectionObserver(function(es){{es.forEach(function(e){{if(e.isIntersecting)e.target.classList.add('visible');}});}},{{threshold:0.08}});
    document.querySelectorAll('.reveal,.feat-card,.test-card,.price-card,.hiw-step').forEach(function(el){{el.classList.add('reveal');io.observe(el);}});
    window.addEventListener('scroll',function(){{document.getElementById('topnav').style.boxShadow=window.scrollY>20?'0 4px 32px rgba(0,0,0,0.22)':'';}} );
</script>
</body>
</html>"""

