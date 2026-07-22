import os
from pathlib import Path

import dotenv
import yaml


class Config:
    DEFAULT_DIR = str(Path.home() / ".boukensha")
    PROMPTS_DIR = str(Path(__file__).resolve().parent / "prompts")

    def __init__(self):
        self.dir = self._resolve_dir()
        self._load_env()
        self.settings = self._load_settings()

    def tasks(self, name=None):
        all_tasks = self._dig("tasks") or {}
        if name is None:
            return all_tasks
        return all_tasks.get(name)

    @property
    def user_prompts_dir(self):
        return os.path.join(self.dir, "prompts")

    @property
    def mud_host(self):
        return self._dig("mud", "host") or "localhost"

    @property
    def mud_port(self):
        return self._dig("mud", "port") or 4000

    @property
    def mud_username(self):
        return self._dig("mud", "username")

    @property
    def mud_password(self):
        return self._dig("mud", "password")

    def _dig(self, *keys):
        node = self.settings
        for key in keys:
            if isinstance(node, dict):
                node = node.get(key)
            else:
                return None
        return node

    def _resolve_dir(self):
        raw = os.environ.get("BOUKENSHA_DIR") or self.DEFAULT_DIR
        return str(Path(raw).resolve())

    def _load_env(self):
        env_file = os.path.join(self.dir, ".env")
        if os.path.isfile(env_file):
            dotenv.load_dotenv(env_file)

    def _load_settings(self):
        settings_file = os.path.join(self.dir, "settings.yaml")
        if os.path.isfile(settings_file):
            with open(settings_file) as f:
                return yaml.safe_load(f) or {}
        return {}

    def __repr__(self):
        task_keys = ", ".join(self.tasks().keys()) if self.tasks() else ""
        return f"<Config dir={self.dir} tasks={task_keys}>"
