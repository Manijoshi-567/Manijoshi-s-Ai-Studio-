import os
import re
import json
import zipfile
import io
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, send_file, render_template_string
from flask_cors import CORS

from generator import LandingPageGenerator
from config import Config

app = Flask(__name__, static_folder="static", template_folder="templates")
CORS(app)

OUTPUT_DIR = Config.OUTPUT_DIR.resolve()
OUTPUT_DIR.mkdir(exist_ok=True)

@app.after_request
def add_security_headers(response):
    """Enforces strict HTTP security headers against common web attacks."""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    response.headers['Permissions-Policy'] = 'geolocation=(), microphone=(), camera=()'
    return response

@app.route("/")
def index():
    return render_template_string(INDEX_HTML)

@app.route("/api/generate", methods=["POST"])
def generate():
    data = request.json or {}
    mode = data.get("mode", "url")
    url_or_concept = data.get("url", "").strip()
    custom_instructions = data.get("custom_instructions", "").strip()
    target_device = data.get("target_device", "desktop").lower()
    color_theme = data.get("color_theme", "cream_purple").lower()
    provider = Config.sanitize_provider(data.get("provider"))
    model = data.get("model", None)
    raw_api_key = data.get("api_key", "").strip()

    if target_device not in ["desktop", "tablet", "mobile"]:
        target_device = "desktop"

    if not url_or_concept:
        return jsonify({"success": False, "error": "Website URL or product description is required"}), 400

    try:
        generator = LandingPageGenerator(
            provider=provider,
            model=model,
            api_key=raw_api_key if raw_api_key else None,
            output_dir=OUTPUT_DIR
        )
        output_file = generator.generate_from_url(
            url_or_concept,
            mode=mode,
            custom_instructions=custom_instructions,
            target_device=target_device,
            color_theme=color_theme
        )
        domain_slug = re.sub(r"[^\w-]", "", output_file.parent.name)

        metadata_file = output_file.parent / "metadata.json"
        metadata = {}
        if metadata_file.exists():
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
            # Security: Ensure raw API key is never exposed in response metadata
            if "api_key" in metadata:
                del metadata["api_key"]

        return jsonify({
            "success": True,
            "domain_slug": domain_slug,
            "target_device": target_device,
            "color_theme": color_theme,
            "preview_url": f"/preview/{domain_slug}",
            "download_url": f"/api/download/{domain_slug}",
            "download_zip_url": f"/api/download_zip/{domain_slug}",
            "metadata": metadata
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/history", methods=["GET"])
def get_history():
    history = []
    if OUTPUT_DIR.exists():
        for project_dir in OUTPUT_DIR.iterdir():
            clean_slug = re.sub(r"[^\w-]", "", project_dir.name)
            if project_dir.is_dir() and (project_dir / "index.html").exists():
                meta_path = project_dir / "metadata.json"
                title = clean_slug.replace("_", ".")
                strategy = {}
                if meta_path.exists():
                    try:
                        data = json.loads(meta_path.read_text(encoding="utf-8"))
                        strategy = data.get("strategy", {})
                        title = strategy.get("product_name", title)
                    except Exception:
                        pass
                
                history.append({
                    "slug": clean_slug,
                    "title": title,
                    "tagline": strategy.get("tagline", "Generated Landing Page"),
                    "preview_url": f"/preview/{clean_slug}"
                })
    return jsonify({"success": True, "history": history})

@app.route("/preview/<domain_slug>")
def preview(domain_slug):
    # Security Guard: sanitize domain_slug & enforce strict directory boundary
    clean_slug = re.sub(r"[^\w-]", "", domain_slug)
    target_dir = (OUTPUT_DIR / clean_slug).resolve()
    
    if not target_dir.exists() or not target_dir.is_relative_to(OUTPUT_DIR) or not (target_dir / "index.html").exists():
        return jsonify({"error": "Access Denied: Invalid path or file not found"}), 403

    return send_from_directory(target_dir, "index.html")

@app.route("/api/download/<domain_slug>")
def download(domain_slug):
    # Security Guard: sanitize domain_slug & enforce strict directory boundary
    clean_slug = re.sub(r"[^\w-]", "", domain_slug)
    target_dir = (OUTPUT_DIR / clean_slug).resolve()
    
    if not target_dir.exists() or not target_dir.is_relative_to(OUTPUT_DIR) or not (target_dir / "index.html").exists():
        return jsonify({"error": "Access Denied: Invalid path or file not found"}), 403

    return send_from_directory(target_dir, "index.html", as_attachment=True, download_name=f"{clean_slug}_landing_page.html")

@app.route("/api/download_zip/<domain_slug>")
def download_zip(domain_slug):
    # Security Guard: sanitize domain_slug & enforce strict directory boundary
    clean_slug = re.sub(r"[^\w-]", "", domain_slug)
    target_dir = (OUTPUT_DIR / clean_slug).resolve()
    
    if not target_dir.exists() or not target_dir.is_relative_to(OUTPUT_DIR) or not (target_dir / "index.html").exists():
        return jsonify({"error": "Access Denied: Invalid path or file not found"}), 403

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add index.html
        html_file = target_dir / "index.html"
        if html_file.exists():
            zf.write(html_file, arcname="index.html")

        # Add metadata.json if present
        meta_file = target_dir / "metadata.json"
        if meta_file.exists():
            zf.write(meta_file, arcname="metadata.json")

        # Add README.md
        readme_text = f"""# {clean_slug.replace('_', ' ').title()} - Landing Page

Generated by **Jo's AI Studio Landing Page Engine**.

## Included Files
- `index.html` - Production-ready HTML5 landing page with embedded CSS, Lucide icons, & Vanilla JS.
- `metadata.json` - Product positioning strategy & structured copywriting data.

## Hosting Instructions
Deploy instantly on Vercel, Netlify, GitHub Pages, or any web server by uploading `index.html`.
"""
        zf.writestr("README.md", readme_text)

    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"{clean_slug}_landing_page.zip"
    )


INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Jo's AI Studio - Landing Page Generator</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Space+Mono:wght@400;700&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <script src="https://unpkg.com/lucide@latest"></script>
    <style>
        :root {
            --bg-cream: #e8e8e2;
            --bg-card: #f1f1ee;
            --ink-dark: #130537;
            --purple-accent: #6818cd;
            --lime-accent: #d4f937;
            --lime-hover: #c4eb22;
            --border-dark: #130537;
            --text-muted: #534575;
        }

        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', sans-serif; }
        body { background-color: var(--bg-cream); color: var(--ink-dark); height: 100vh; display: flex; flex-direction: column; overflow: hidden; }

        /* Jo's AI Studio Header */
        header { background: var(--bg-cream); border-bottom: 1.5px solid var(--border-dark); padding: 0.8rem 2rem; display: flex; justify-content: space-between; align-items: center; z-index: 50; }
        .brand { display: flex; align-items: center; gap: 0.8rem; font-family: 'Space Grotesk', sans-serif; font-size: 1.4rem; font-weight: 700; color: var(--ink-dark); letter-spacing: -0.02em; }
        .brand-badge { font-size: 0.72rem; font-family: 'Space Mono', monospace; text-transform: uppercase; padding: 0.25rem 0.65rem; background: var(--bg-card); border: 1px solid var(--border-dark); color: var(--ink-dark); font-weight: 700; }
        
        .header-tag { font-family: 'Space Mono', monospace; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.05em; color: var(--ink-dark); font-weight: 700; display: flex; align-items: center; gap: 0.5rem; }

        /* Workspace Grid */
        .workspace { flex: 1; display: grid; grid-template-columns: 440px 1fr; height: calc(100vh - 65px); overflow: hidden; }

        /* Left Control Panel */
        .sidebar { background: var(--bg-cream); border-right: 1.5px solid var(--border-dark); padding: 1.4rem; display: flex; flex-direction: column; gap: 0.85rem; overflow-y: auto; }
        
        /* Mode Tabs */
        .mode-tabs { display: flex; background: var(--bg-card); padding: 0.25rem; border: 1.5px solid var(--border-dark); margin-bottom: 0.2rem; }
        .mode-tab { flex: 1; padding: 0.55rem 0.5rem; text-align: center; font-family: 'Space Mono', monospace; font-size: 0.78rem; text-transform: uppercase; font-weight: 700; cursor: pointer; color: var(--ink-dark); transition: all 0.2s; display: flex; align-items: center; justify-content: center; gap: 0.4rem; border: 1px solid transparent; }
        .mode-tab.active { background: var(--ink-dark); color: var(--bg-cream); border-color: var(--border-dark); }

        .form-group { display: flex; flex-direction: column; gap: 0.3rem; }
        label { font-family: 'Space Mono', monospace; font-size: 0.75rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; color: var(--ink-dark); }
        input, select, textarea { width: 100%; padding: 0.65rem 0.85rem; background: var(--bg-card); border: 1.5px solid var(--border-dark); color: var(--ink-dark); font-size: 0.9rem; outline: none; transition: all 0.2s; font-family: 'Inter', sans-serif; }
        input:focus, select:focus, textarea:focus { background: #ffffff; box-shadow: 2px 2px 0px var(--ink-dark); }
        
        .presets { display: flex; gap: 0.35rem; flex-wrap: wrap; margin-top: 0.2rem; }
        .chip { padding: 0.25rem 0.6rem; background: var(--bg-card); border: 1px solid var(--border-dark); font-family: 'Space Mono', monospace; font-size: 0.72rem; cursor: pointer; color: var(--ink-dark); font-weight: 700; text-transform: uppercase; transition: all 0.2s; }
        .chip:hover { background: var(--lime-accent); }

        /* UI/UX Color Theme Selector Swatches */
        .color-themes { display: grid; grid-template-columns: repeat(5, 1fr); gap: 0.35rem; margin-top: 0.2rem; }
        .color-theme-card { padding: 0.4rem 0.2rem; background: var(--bg-card); border: 1.5px solid var(--border-dark); text-align: center; cursor: pointer; transition: all 0.2s; display: flex; flex-direction: column; align-items: center; gap: 0.3rem; }
        .color-theme-card.active { border-color: var(--purple-accent); background: #ffffff; box-shadow: 2px 2px 0px var(--border-dark); }
        .color-dots { display: flex; gap: 3px; }
        .color-dot { width: 12px; height: 12px; border-radius: 50%; border: 1px solid rgba(0,0,0,0.2); }
        .theme-name { font-family: 'Space Mono', monospace; font-size: 0.62rem; font-weight: 700; text-transform: uppercase; color: var(--ink-dark); }

        /* Target Device Selector Pills */
        .device-pills { display: flex; gap: 0.35rem; margin-top: 0.1rem; }
        .device-pill { flex: 1; padding: 0.5rem; text-align: center; background: var(--bg-card); border: 1.5px solid var(--border-dark); font-family: 'Space Mono', monospace; font-size: 0.72rem; font-weight: 700; text-transform: uppercase; cursor: pointer; color: var(--ink-dark); transition: all 0.2s; display: flex; align-items: center; justify-content: center; gap: 0.3rem; }
        .device-pill.active { background: var(--purple-accent); color: white; border-color: var(--border-dark); box-shadow: 2px 2px 0px var(--border-dark); }

        /* Jo's AI Studio Lime Button */
        .btn-generate { width: 100%; padding: 0.85rem; background: var(--lime-accent); border: 1.5px solid var(--border-dark); color: var(--ink-dark); font-family: 'Space Grotesk', sans-serif; font-weight: 700; font-size: 0.98rem; text-transform: uppercase; letter-spacing: 0.03em; cursor: pointer; transition: all 0.2s; display: flex; justify-content: center; align-items: center; gap: 0.6rem; margin-top: 0.3rem; }
        .btn-generate:hover { background: var(--lime-hover); transform: translate(-2px, -2px); box-shadow: 4px 4px 0px var(--border-dark); }
        .btn-generate:disabled { opacity: 0.5; cursor: not-allowed; transform: none; box-shadow: none; }

        /* Execution Stepper */
        .stepper { display: flex; flex-direction: column; gap: 0.4rem; margin-top: 0.2rem; }
        .step-item { display: flex; align-items: center; gap: 0.75rem; padding: 0.55rem 0.75rem; background: var(--bg-card); border: 1px solid var(--border-dark); transition: all 0.3s; }
        .step-item.active { background: #ffffff; border-width: 1.5px; box-shadow: 2px 2px 0px var(--ink-dark); }
        .step-item.completed { background: #e2f8d8; border-color: #1b5e20; }
        .step-icon { width: 24px; height: 24px; border-radius: 4px; display: flex; align-items: center; justify-content: center; background: var(--bg-cream); border: 1px solid var(--border-dark); font-size: 0.78rem; }
        .step-info h4 { font-family: 'Space Grotesk', sans-serif; font-size: 0.8rem; font-weight: 700; color: var(--ink-dark); }
        .step-info p { font-size: 0.68rem; color: var(--text-muted); }

        /* Canvas Preview Area */
        .canvas-area { background: #dcdcd4; display: flex; flex-direction: column; overflow: hidden; position: relative; }
        .canvas-toolbar { background: var(--bg-cream); border-bottom: 1.5px solid var(--border-dark); padding: 0.6rem 1.2rem; display: flex; justify-content: space-between; align-items: center; }
        
        .url-bar { background: #ffffff; border: 1px solid var(--border-dark); padding: 0.35rem 0.9rem; font-family: 'Space Mono', monospace; font-size: 0.76rem; color: var(--ink-dark); width: 310px; text-overflow: ellipsis; overflow: hidden; white-space: nowrap; }
        
        .actions { display: flex; gap: 0.5rem; }
        .action-btn { padding: 0.45rem 0.85rem; background: var(--bg-card); border: 1.5px solid var(--border-dark); color: var(--ink-dark); font-family: 'Space Grotesk', sans-serif; font-size: 0.8rem; font-weight: 700; text-transform: uppercase; cursor: pointer; text-decoration: none; display: flex; align-items: center; gap: 0.35rem; transition: all 0.2s; }
        .action-btn:hover { background: var(--lime-accent); transform: translate(-1px, -1px); box-shadow: 2px 2px 0px var(--border-dark); }
        .action-btn-zip { background: var(--purple-accent); color: white; }
        .action-btn-zip:hover { background: #5512aa; color: white; }

        .iframe-container { flex: 1; display: flex; justify-content: center; align-items: center; padding: 1rem; overflow: auto; }
        iframe { width: 100%; height: 100%; border: 1.5px solid var(--border-dark); background: white; transition: all 0.3s ease; box-shadow: 4px 4px 0px var(--border-dark); }
        iframe.desktop-mode { width: 100%; height: 100%; }
        iframe.tablet-mode { width: 768px; height: 95%; }
        iframe.mobile-mode { width: 375px; height: 95%; }

        .empty-state { display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; text-align: center; color: var(--ink-dark); padding: 2rem; }
        .empty-icon { width: 80px; height: 80px; background: var(--bg-card); border: 1.5px solid var(--border-dark); display: flex; align-items: center; justify-content: center; color: var(--purple-accent); margin-bottom: 1.5rem; box-shadow: 3px 3px 0px var(--border-dark); }
        .empty-title { font-family: 'Space Grotesk', sans-serif; font-size: 1.8rem; font-weight: 700; text-transform: uppercase; margin-bottom: 0.5rem; }

        /* Spinner */
        .spinner { border: 2.5px solid rgba(19, 5, 55, 0.2); border-top: 2.5px solid var(--ink-dark); border-radius: 50%; width: 18px; height: 18px; animation: spin 0.8s linear infinite; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
    </style>
</head>
<body>
    <header>
        <div class="brand">
            <i data-lucide="layers" style="color: var(--purple-accent)"></i> Jo's AI Studio
            <span class="brand-badge">Landing Page Engine</span>
        </div>
        <div class="header-tag">
            <i data-lucide="lock" style="width: 14px; height: 14px; color: var(--purple-accent);"></i>
            <span>Admin Model Protected</span> • <span style="color: var(--purple-accent)">In-Memory Secure</span>
        </div>
    </header>

    <div class="workspace">
        <div class="sidebar">
            <div class="mode-tabs">
                <div class="mode-tab active" id="tabUrl" onclick="switchMode('url')">
                    <i data-lucide="link"></i> Reference URL
                </div>
                <div class="mode-tab" id="tabDesc" onclick="switchMode('description')">
                    <i data-lucide="edit-3"></i> Custom Prompt
                </div>
            </div>

            <!-- Mode 1: Website URL -->
            <div id="urlModePanel">
                <div class="form-group">
                    <label>Website URL to Re-Imagine</label>
                    <input type="text" id="targetUrl" placeholder="e.g. https://stripe.com or https://youtube.com">
                    <div class="presets">
                        <span class="chip" onclick="setPreset('https://youtube.com')">YouTube</span>
                        <span class="chip" onclick="setPreset('https://github.com')">GitHub</span>
                        <span class="chip" onclick="setPreset('https://stripe.com')">Stripe</span>
                        <span class="chip" onclick="setPreset('https://linear.app')">Linear</span>
                    </div>
                </div>
                <div class="form-group" style="margin-top: 0.5rem;">
                    <label>What to improve / customize? (Optional)</label>
                    <input type="text" id="urlInstructions" placeholder="e.g. Make it dark mode with glowing purple buttons">
                </div>
            </div>

            <!-- Mode 2: Custom Text Prompt -->
            <div id="descModePanel" style="display: none;">
                <div class="form-group">
                    <label>Describe Your Landing Page</label>
                    <textarea id="customPrompt" rows="3" placeholder="e.g. A crypto trading platform with bold components, dark theme, and high-converting feature grid."></textarea>
                </div>
            </div>

            <!-- Popular UI/UX Color Themes Selector -->
            <div class="form-group">
                <label>Popular UI/UX Color Schemes</label>
                <div class="color-themes">
                    <div class="color-theme-card active" id="theme_cream_purple" onclick="selectTheme('cream_purple')">
                        <div class="color-dots">
                            <div class="color-dot" style="background: #6818cd;"></div>
                            <div class="color-dot" style="background: #d4f937;"></div>
                        </div>
                        <span class="theme-name">Jo Studio</span>
                    </div>
                    <div class="color-theme-card" id="theme_cyberpunk_neon" onclick="selectTheme('cyberpunk_neon')">
                        <div class="color-dots">
                            <div class="color-dot" style="background: #00f2fe;"></div>
                            <div class="color-dot" style="background: #f000ff;"></div>
                        </div>
                        <span class="theme-name">Cyberpunk</span>
                    </div>
                    <div class="color-theme-card" id="theme_emerald_tech" onclick="selectTheme('emerald_tech')">
                        <div class="color-dots">
                            <div class="color-dot" style="background: #10b981;"></div>
                            <div class="color-dot" style="background: #06b6d4;"></div>
                        </div>
                        <span class="theme-name">Emerald</span>
                    </div>
                    <div class="color-theme-card" id="theme_indigo_saas" onclick="selectTheme('indigo_saas')">
                        <div class="color-dots">
                            <div class="color-dot" style="background: #6366f1;"></div>
                            <div class="color-dot" style="background: #a855f7;"></div>
                        </div>
                        <span class="theme-name">Indigo SaaS</span>
                    </div>
                    <div class="color-theme-card" id="theme_sunset_amber" onclick="selectTheme('sunset_amber')">
                        <div class="color-dots">
                            <div class="color-dot" style="background: #ff5e36;"></div>
                            <div class="color-dot" style="background: #f59e0b;"></div>
                        </div>
                        <span class="theme-name">Sunset</span>
                    </div>
                </div>
            </div>

            <!-- Target Device Selector -->
            <div class="form-group">
                <label>Target Device Layout</label>
                <div class="device-pills">
                    <div class="device-pill active" id="pillDesk" onclick="selectDevice('desktop')"><i data-lucide="monitor"></i> Desktop</div>
                    <div class="device-pill" id="pillTab" onclick="selectDevice('tablet')"><i data-lucide="tablet"></i> Tablet</div>
                    <div class="device-pill" id="pillMob" onclick="selectDevice('mobile')"><i data-lucide="smartphone"></i> Mobile</div>
                </div>
            </div>

            <div class="form-group">
                <label>AI Model Provider</label>
                <select id="provider">
                    <option value="openai">OpenAI (gpt-4o-mini)</option>
                    <option value="gemini">Google Gemini (gemini-1.5-flash)</option>
                    <option value="anthropic">Anthropic Claude</option>
                    <option value="ollama">Local Ollama (llama3)</option>
                </select>
            </div>

            <div class="form-group">
                <label>API Key (Optional / Auto-Fallback)</label>
                <input type="password" id="apiKey" placeholder="Leave blank to use Smart Engine">
            </div>

            <button class="btn-generate" id="btnGenerate" onclick="startGeneration()">
                <i data-lucide="zap"></i> Generate Landing Page
            </button>

            <div style="margin-top: 0.1rem;">
                <label>Agent Execution Timeline</label>
                <div class="stepper">
                    <div class="step-item" id="step1">
                        <div class="step-icon"><i data-lucide="globe"></i></div>
                        <div class="step-info">
                            <h4>1. Input & Web Scraper Agent</h4>
                            <p>Parses reference site or prompt details</p>
                        </div>
                    </div>
                    <div class="step-item" id="step2">
                        <div class="step-icon"><i data-lucide="brain"></i></div>
                        <div class="step-info">
                            <h4>2. Product Strategist Agent</h4>
                            <p>Synthesizes personas & positioning</p>
                        </div>
                    </div>
                    <div class="step-item" id="step3">
                        <div class="step-icon"><i data-lucide="pen-tool"></i></div>
                        <div class="step-info">
                            <h4>3. Conversion Copywriter</h4>
                            <p>Generates high-converting text</p>
                        </div>
                    </div>
                    <div class="step-item" id="step4">
                        <div class="step-icon"><i data-lucide="code"></i></div>
                        <div class="step-info">
                            <h4>4. UI/UX Architect Agent</h4>
                            <p>Renders responsive HTML/CSS page</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <div class="canvas-area">
            <div class="canvas-toolbar">
                <div class="device-selector">
                    <span style="font-family: 'Space Mono', monospace; font-size: 0.75rem; font-weight: 700; text-transform: uppercase;">PREVIEW VIEWPORT:</span>
                </div>
                <div class="url-bar" id="urlDisplay">http://localhost/preview/demo</div>
                <div class="actions">
                    <button class="action-btn" id="openTabBtn" onclick="openFullTab()"><i data-lucide="external-link"></i> Fullscreen</button>
                    <a class="action-btn action-btn-zip" id="downloadZipBtn" href="#" download><i data-lucide="file-archive"></i> Download ZIP</a>
                    <a class="action-btn" id="downloadBtn" href="#" download><i data-lucide="file-code"></i> HTML File</a>
                </div>
            </div>

            <div class="iframe-container">
                <div id="emptyState" class="empty-state">
                    <div class="empty-icon"><i data-lucide="layout" style="width: 40px; height: 40px;"></i></div>
                    <h2 class="empty-title">Welcome to Jo's AI Studio</h2>
                    <p>Select <strong>Reference URL</strong> or <strong>Custom Prompt</strong> on the left panel and click <strong>Generate Landing Page</strong>.</p>
                </div>

                <iframe id="previewFrame" class="desktop-mode" style="display: none;"></iframe>
            </div>
        </div>
    </div>

    <script>
        lucide.createIcons();
        let currentMode = "url";
        let targetDevice = "desktop";
        let selectedColorTheme = "cream_purple";
        let currentPreviewUrl = "";

        function switchMode(mode) {
            currentMode = mode;
            document.getElementById("tabUrl").className = mode === "url" ? "mode-tab active" : "mode-tab";
            document.getElementById("tabDesc").className = mode === "description" ? "mode-tab active" : "mode-tab";

            document.getElementById("urlModePanel").style.display = mode === "url" ? "block" : "none";
            document.getElementById("descModePanel").style.display = mode === "description" ? "block" : "none";
        }

        function selectDevice(device) {
            targetDevice = device;
            document.getElementById("pillDesk").className = device === "desktop" ? "device-pill active" : "device-pill";
            document.getElementById("pillTab").className = device === "tablet" ? "device-pill active" : "device-pill";
            document.getElementById("pillMob").className = device === "mobile" ? "device-pill active" : "device-pill";

            const frame = document.getElementById("previewFrame");
            frame.className = device + "-mode";
        }

        function selectTheme(theme) {
            selectedColorTheme = theme;
            const themes = ["cream_purple", "cyberpunk_neon", "emerald_tech", "indigo_saas", "sunset_amber"];
            themes.forEach(t => {
                const el = document.getElementById("theme_" + t);
                if (el) el.className = t === theme ? "color-theme-card active" : "color-theme-card";
            });
        }

        function setPreset(url) {
            document.getElementById("targetUrl").value = url;
        }

        async function startGeneration() {
            let inputTarget = "";
            let instructions = "";

            if (currentMode === "url") {
                inputTarget = document.getElementById("targetUrl").value.trim();
                instructions = document.getElementById("urlInstructions").value.trim();
                if (!inputTarget) {
                    alert("Please enter a reference website URL!");
                    return;
                }
            } else {
                inputTarget = document.getElementById("customPrompt").value.trim();
                instructions = "Aesthetic: " + selectedColorTheme;
                if (!inputTarget) {
                    alert("Please describe how you want your landing page to be!");
                    return;
                }
            }

            const btn = document.getElementById("btnGenerate");
            btn.disabled = true;
            btn.innerHTML = `<div class="spinner"></div> Generating for ${targetDevice.toUpperCase()}...`;

            resetSteps();
            
            // Animate Stepper steps
            setStepStatus("step1", "active");
            setTimeout(() => setStepStatus("step1", "completed"), 1200);

            setTimeout(() => setStepStatus("step2", "active"), 1300);
            setTimeout(() => setStepStatus("step2", "completed"), 2400);

            setTimeout(() => setStepStatus("step3", "active"), 2500);
            setTimeout(() => setStepStatus("step3", "completed"), 3600);

            setTimeout(() => setStepStatus("step4", "active"), 3700);

            try {
                const response = await fetch("/api/generate", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        mode: currentMode,
                        url: inputTarget,
                        custom_instructions: instructions,
                        target_device: targetDevice,
                        color_theme: selectedColorTheme,
                        provider: document.getElementById("provider").value,
                        api_key: document.getElementById("apiKey").value.trim()
                    })
                });

                const data = await response.json();
                if (data.success) {
                    setStepStatus("step4", "completed");
                    currentPreviewUrl = data.preview_url;
                    
                    document.getElementById("emptyState").style.display = "none";
                    const frame = document.getElementById("previewFrame");
                    frame.style.display = "block";
                    frame.className = targetDevice + "-mode";
                    frame.src = data.preview_url;

                    document.getElementById("urlDisplay").innerText = window.location.origin + data.preview_url;
                    document.getElementById("downloadBtn").href = data.download_url;
                    document.getElementById("downloadZipBtn").href = data.download_zip_url;
                } else {
                    alert("Generation failed: " + data.error);
                }
            } catch (err) {
                alert("Error connecting to server: " + err.message);
            } finally {
                btn.disabled = false;
                btn.innerHTML = `<i data-lucide="zap"></i> Generate Landing Page`;
                lucide.createIcons();
            }
        }

        function resetSteps() {
            for (let i = 1; i <= 4; i++) {
                const el = document.getElementById("step" + i);
                el.className = "step-item";
            }
        }

        function setStepStatus(stepId, status) {
            const el = document.getElementById(stepId);
            el.className = `step-item ${status}`;
        }

        function openFullTab() {
            if (currentPreviewUrl) {
                window.open(currentPreviewUrl, "_blank");
            }
        }
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    print("\n🌐 Starting Jo's AI Studio Web App Server...")
    print("🚀 Open http://localhost:5000 in your web browser!\n")
    app.run(host="0.0.0.0", port=5000, debug=True)
