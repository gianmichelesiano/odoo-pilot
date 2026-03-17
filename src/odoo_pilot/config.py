from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Settings:
    dry_run: bool = True
    playwright_timeout: int = 30000  # ms
    max_pages: int = 50
    request_delay: float = 1.0  # seconds between page requests
    output_dir: Path = field(default_factory=lambda: Path("output"))

    # Odoo connection (Phase 3)
    odoo_url: str = ""
    odoo_db: str = ""
    odoo_user: str = ""
    odoo_password: str = ""

    # AI config (Phase 2)
    anthropic_model: str = "claude-sonnet-4-6"
    ollama_model: str = "llama3.1"
    use_ollama: bool = False  # fallback flag
