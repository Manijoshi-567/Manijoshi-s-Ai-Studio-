# Security Policy — Joshi's AI Studio

## 🛡️ Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.0.x   | ✅ Active Support  |
| < 1.0   | ❌ No Support      |

## 🔐 Security Architecture

### API Key Protection
- API keys are **never persisted to disk** or stored in any database
- Keys are loaded from environment variables at startup and held in-memory only
- API keys are automatically stripped from all JSON responses and metadata outputs
- The `.env` file is excluded from version control via `.gitignore`

### Input Sanitization
- All `domain_slug` parameters are sanitized with `re.sub(r"[^\w-]", "", ...)`
- Directory traversal attacks are blocked via `Path.is_relative_to(OUTPUT_DIR)` guards
- LLM provider names are validated against an allowlist (`Config.ALLOWED_PROVIDERS`)

### HTTP Security Headers
Every response includes:
- `X-Content-Type-Options: nosniff`
- `X-XSS-Protection: 1; mode=block`
- `X-Frame-Options: SAMEORIGIN`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: geolocation=(), microphone=(), camera=()`

### Admin Access Control
- Model configuration updates are locked via `Config.ADMIN_LOCK_ENABLED = True`
- Only the repository owner can modify agent prompts, pipeline logic, and security settings
- No remote administration endpoints are exposed

## 🚨 Reporting Vulnerabilities

If you discover a security vulnerability, please report it **privately**:

1. **Do NOT** create a public GitHub issue
2. Email the repository owner directly
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact assessment

We will respond within **48 hours** and issue a fix within **7 days** for critical vulnerabilities.

## 🔍 Security Checklist for Contributors

- [ ] No API keys or secrets in code
- [ ] All user inputs are sanitized
- [ ] File paths are validated against OUTPUT_DIR boundary
- [ ] No `eval()` or `exec()` on user input
- [ ] HTTP security headers are preserved
