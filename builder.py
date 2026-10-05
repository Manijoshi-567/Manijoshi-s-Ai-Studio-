import os
import json
import http.server
import socketserver
import webbrowser
from pathlib import Path
from typing import Dict, Any

class SiteBuilder:
    def __init__(self, output_dir: Path = Path("output")):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def save_landing_page(self, domain_slug: str, html_content: str, strategy: Dict[str, Any], copy: Dict[str, Any]) -> Path:
        """Saves the generated HTML landing page and metadata to disk."""
        project_dir = self.output_dir / domain_slug
        project_dir.mkdir(parents=True, exist_ok=True)

        index_file = project_dir / "index.html"
        metadata_file = project_dir / "metadata.json"

        # Write HTML
        index_file.write_text(html_content, encoding="utf-8")

        # Write metadata
        metadata = {
            "domain_slug": domain_slug,
            "strategy": strategy,
            "copy": copy,
            "generated_file": str(index_file.resolve())
        }
        metadata_file.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

        return index_file

    @staticmethod
    def serve_preview(target_dir: Path, port: int = 8000):
        """Starts a local HTTP web server to preview the generated landing page."""
        os.chdir(target_dir)
        handler = http.server.SimpleHTTPRequestHandler

        print(f"\n🚀 Server running at: http://localhost:{port}")
        print("Press Ctrl+C to stop the preview server.\n")

        webbrowser.open(f"http://localhost:{port}")

        with socketserver.TCPServer(("", port), handler) as httpd:
            try:
                httpd.serve_forever()
            except KeyboardInterrupt:
                print("\nServer stopped.")
