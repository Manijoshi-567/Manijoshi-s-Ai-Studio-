# Contributing to Joshi's AI Studio

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing.

## 🔒 Important: Access Control

This project uses **admin-locked model configuration**. Only the repository owner can modify:
- LLM provider configurations (`config.py`)
- Agent prompt engineering (`agents.py`)
- Pipeline orchestration logic (`generator.py`)
- Security headers and API endpoint logic (`app.py`)

## 🐛 Reporting Issues

1. Check existing issues to avoid duplicates
2. Use the issue template and include:
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python version, LLM provider)

## 🔧 Development Setup

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/joshis-ai-studio.git
cd joshis-ai-studio

# Create virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env with your API keys
```

## 📝 Pull Request Guidelines

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit changes with clear messages
4. Ensure no API keys or secrets are committed
5. Submit a PR with a clear description

## 🛡️ Security

- **NEVER** commit `.env` files or API keys
- All API keys are processed in-memory only
- Report security vulnerabilities privately via email

## 📜 Code of Conduct

Be respectful, inclusive, and constructive in all interactions.
