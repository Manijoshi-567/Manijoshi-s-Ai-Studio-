import sys
import io
import argparse
from pathlib import Path

# Force UTF-8 stdout encoding for Windows console compatibility
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel

from config import Config
from generator import LandingPageGenerator
from builder import SiteBuilder

console = Console()


def main():
    banner = """
    [bold magenta]=====================================================[/bold magenta]
    [bold white]   🤖 AI LANDING PAGE GENERATOR AGENT SYSTEM   [/bold white]
    [bold magenta]=====================================================[/bold magenta]
    """
    console.print(banner)

    parser = argparse.ArgumentParser(description="Auto-generate landing pages for any website or product idea.")
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Command: generate
    gen_parser = subparsers.add_parser("generate", help="Generate a landing page for a website or concept")
    gen_parser.add_argument("-u", "--url", type=str, required=True, help="Website URL (e.g. https://stripe.com) or product description prompt")
    gen_parser.add_argument("-p", "--provider", type=str, default=Config.DEFAULT_PROVIDER, choices=["openai", "gemini", "anthropic", "ollama"], help="LLM Provider")
    gen_parser.add_argument("-m", "--model", type=str, default=None, help="LLM Model Name (e.g., gpt-4o-mini, gemini-1.5-flash)")
    gen_parser.add_argument("-k", "--api-key", type=str, default=None, help="API key for the selected provider")
    gen_parser.add_argument("-o", "--output", type=str, default="output", help="Output directory path")
    gen_parser.add_argument("--preview", action="store_true", help="Automatically launch live browser preview after generation")

    # Command: preview
    prev_parser = subparsers.add_parser("preview", help="Preview an existing generated landing page in browser")
    prev_parser.add_argument("-d", "--dir", type=str, required=True, help="Path to project directory containing index.html")
    prev_parser.add_argument("--port", type=int, default=8000, help="Local server port")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "generate":
        output_dir = Path(args.output)
        generator = LandingPageGenerator(
            provider=args.provider,
            model=args.model,
            api_key=args.api_key,
            output_dir=output_dir
        )
        
        output_file = generator.generate_from_url(args.url)

        if args.preview:
            project_dir = output_file.parent
            SiteBuilder.serve_preview(project_dir)

    elif args.command == "preview":
        target_dir = Path(args.dir)
        if not (target_dir / "index.html").exists():
            console.print(f"[bold red]Error:[/bold red] index.html not found in '{target_dir}'")
            sys.exit(1)

        SiteBuilder.serve_preview(target_dir, port=args.port)

if __name__ == "__main__":
    main()
