import os


class Base:
    task_name = None

    @classmethod
    def _fetch(cls, settings, key):
        return settings.get(key)

    @classmethod
    def provider(cls, settings):
        value = cls._fetch(settings, "provider")
        if not value:
            raise ValueError(f"tasks.{cls.task_name}.provider is required in settings.yaml")
        return value

    @classmethod
    def model(cls, settings):
        value = cls._fetch(settings, "model")
        if not value:
            raise ValueError(f"tasks.{cls.task_name}.model is required in settings.yaml")
        return value

    @classmethod
    def prompt_override(cls, settings, prompt="system"):
        node = cls._fetch(settings, "prompt_override")
        if not isinstance(node, dict):
            return False
        return node.get(prompt) is True

    @classmethod
    def _read_file(cls, path):
        return open(path).read().strip() if os.path.isfile(path) else None

    @classmethod
    def _read_user_prompt(cls, prompt_name, user_prompts_dir=None):
        if not user_prompts_dir:
            return None
        return cls._read_file(os.path.join(user_prompts_dir, cls.task_name, f"{prompt_name}.md"))

    @classmethod
    def _read_default_prompt(cls, prompt_name, default_prompts_dir=None):
        if not default_prompts_dir:
            return None
        return cls._read_file(os.path.join(default_prompts_dir, f"{prompt_name}.md"))

    @classmethod
    def prompt(cls, settings, name="system", user_prompts_dir=None, default_prompts_dir=None):
        if cls.prompt_override(settings, name):
            text = cls._read_user_prompt(name, user_prompts_dir=user_prompts_dir)
            if text:
                return text
        return cls._read_default_prompt(name, default_prompts_dir=default_prompts_dir)

    @classmethod
    def max_iterations(cls, settings):
        return cls._integer_setting(settings, "max_iterations", 25)

    @classmethod
    def max_output_tokens(cls, settings):
        return cls._integer_setting(settings, "max_output_tokens", 1024)

    @classmethod
    def system_prompt(cls, settings, user_prompts_dir=None, default_prompts_dir=None):
        return cls.prompt(settings, "system", user_prompts_dir=user_prompts_dir, default_prompts_dir=default_prompts_dir)

    @classmethod
    def _integer_setting(cls, settings, key, default):
        value = cls._fetch(settings, key)
        return int(value) if value is not None else default
