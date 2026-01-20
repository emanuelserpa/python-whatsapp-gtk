"""
Configuration management.
"""
import json
import logging
from pathlib import Path
from typing import Dict
from .constants import DEFAULT_USER_AGENT

def load_or_create_config(base_path: Path) -> Dict[str, str]:
    """Carrega as configurações do arquivo JSON ou cria um novo com valores padrão."""
    config_file = base_path / "config.json"
    default_config = {
        "user_agent": DEFAULT_USER_AGENT
    }

    if not config_file.exists():
        try:
            with open(config_file, 'w') as f:
                json.dump(default_config, f, indent=4)
            logging.info(f"Arquivo de configuração criado em: {config_file}")
            return default_config
        except Exception as e:
            logging.error(f"Falha ao criar arquivo de configuração: {e}")
            return default_config

    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
            # Garante que chaves essenciais existam (merge com defaults)
            for key, value in default_config.items():
                if key not in config:
                    config[key] = value
            return config
    except Exception as e:
        logging.error(f"Falha ao ler arquivo de configuração: {e}. Usando padrões.")
        return default_config
