import os
from pathlib import Path

import yaml
from dotenv import load_dotenv


_cwd_boukensha = os.path.join(os.getcwd(), ".boukensha")
DEFAULT_DIR = _cwd_boukensha if os.path.isdir(_cwd_boukensha) else os.path.join(os.path.expanduser("~"), ".boukensha")


class Config:
    def __init__(self, dir=None):
        self.dir = (
            os.environ.get("BOUKENSHA_DIR")
            or dir
            or DEFAULT_DIR
        )
        self.dir = str(Path(self.dir).expanduser().resolve())
        self._load_env()
        self.settings = self._load_settings()
        self.system_prompt = self._load_system_prompt()

    def provider_type(self):
        return self._dig("tasks", "player", "provider") or "anthropic"

    def model(self):
        return self._dig("tasks", "player", "model") or "claude-haiku-4-5"

    def system_override(self):
        return self._dig("system", "override") is True

    def mud_host(self):
        return self._dig("mud", "host") or "localhost"

    def mud_port(self):
        return self._dig("mud", "port") or 4000

    def mud_username(self):
        return self._dig("mud", "username")

    def mud_password(self):
        return self._dig("mud", "password")

    def agent_max_iterations(self):
        v = self._dig("agent", "max_iterations")
        return int(v) if v is not None else 25

    def agent_max_output_tokens(self):
        v = self._dig("agent", "max_output_tokens")
        return int(v) if v is not None else 1024

    def agent_max_turn_tokens(self):
        v = self._dig("agent", "max_turn_tokens")
        return int(v) if v is not None else 60_000

    def agent_compaction_threshold(self):
        v = self._dig("agent", "compaction_threshold")
        return float(v) if v is not None else 0.85

    def _load_env(self):
        env_file = os.path.join(self.dir, ".env")
        if os.path.isfile(env_file):
            load_dotenv(env_file)

    def _load_settings(self):
        settings_file = os.path.join(self.dir, "settings.yaml")
        if os.path.isfile(settings_file):
            with open(settings_file, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data if isinstance(data, dict) else {}
        return {}

    def _load_system_prompt(self):
        if self._dig("tasks", "player", "prompt_override", "system") is True:
            task_file = os.path.join(self.dir, "prompts", "player", "system.md")
            if os.path.isfile(task_file):
                with open(task_file, encoding="utf-8") as f:
                    return f.read().strip()

        system_file = os.path.join(self.dir, "prompts", "system.md")
        if os.path.isfile(system_file):
            with open(system_file, encoding="utf-8") as f:
                return f.read().strip()
        return None

    def _dig(self, *keys):
        node = self.settings
        for key in keys:
            if isinstance(node, dict):
                node = node.get(key)
            else:
                return None
        return node

    def __repr__(self):
        return f"<Config dir={self.dir} provider={self.provider_type()} model={self.model()}>"

    __str__ = __repr__
