"""
Utility functions for file paths and system operations.
"""
import sys
import logging
from pathlib import Path
from gi.repository import GLib
from .constants import APP_NAME

def get_app_data_path() -> Path:
    """Retorna o diretório padrão do usuário (XDG Standard) para dados da aplicação."""
    path = Path(GLib.get_user_data_dir()) / APP_NAME
    try:
        path.mkdir(parents=True, exist_ok=True)
        return path
    except OSError as error:
        sys.stderr.write(f"CRITICAL: Falha ao criar repositório de dados: {error}\n")
        sys.exit(1)

def setup_logging(base_path: Path):
    """Configura o sistema de logs."""
    log_file = base_path / "application.log"
    logging.basicConfig(
        filename=str(log_file),
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
