import json
import os
import sys
import pathlib

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if "BOUKENSHA_DIR" not in os.environ:
    repo_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    )
    os.environ["BOUKENSHA_DIR"] = os.path.join(repo_root, ".boukensha")

from boukensha.backends.anthropic import Anthropic
from boukensha.backends.gemini import Gemini
from boukensha.backends.ollama import Ollama
from boukensha.backends.ollama_cloud import OllamaCloud
from boukensha.backends.opencode import OpenCode
from boukensha.backends.openai import OpenAI
from boukensha.client import Client
from boukensha.config import Config
from boukensha.context import Context
from boukensha.prompt_builder import PromptBuilder
from boukensha.registry import Registry
from boukensha.tasks.player import Player

config = Config()
player_settings = config.tasks("player")
system_prompt = Player.system_prompt(
    player_settings,
    user_prompts_dir=config.user_prompts_dir,
    default_prompts_dir=Config.PROMPTS_DIR,
)

ctx = Context(task=Player, system=system_prompt)
registry = Registry(ctx)

registry.tool(
    "read_file",
    description="Read the contents of a file from disk",
    parameters={"path": {"type": "string", "description": "The file path to read"}},
    block=lambda path: pathlib.Path(path).read_text(encoding="utf-8"),
)

registry.tool(
    "list_directory",
    description="List files in a directory",
    parameters={"path": {"type": "string", "description": "The directory path to list"}},
    block=lambda path: "\n".join(
        f for f in os.listdir(path) if not f.startswith(".")
    ),
)

ctx.add_message("user", "What files are in the current directory?")

print("=== BOUKENSHA Step 4: API Client ===")
print()

provider = Player.provider(player_settings)
model = Player.model(player_settings)

backend_map = {
    "anthropic": Anthropic,
    "gemini": Gemini,
    "ollama": Ollama,
    "ollama_cloud": OllamaCloud,
    "opencode": OpenCode,
    "openai": OpenAI,
}

backend_cls = backend_map.get(provider)
if backend_cls is None:
    raise ValueError(f"Unsupported provider for player task: {provider}")

if provider == "ollama":
    backend = backend_cls(model=model)
elif provider in ("anthropic", "gemini", "openai", "opencode", "ollama_cloud"):
    key_var = f"{provider.upper()}_API_KEY"
    backend = backend_cls(api_key=os.environ[key_var], model=model)
else:
    raise ValueError(f"Unsupported provider for player task: {provider}")

builder = PromptBuilder(ctx, backend)
client = Client(builder)

print(f"Config: {config}")
print(f"Provider: {provider}")
print(f"Model: {model}")
print(f"Sending request to {builder.url()}...")
print()

response = client.call()
print("Raw response:")
print(json.dumps(response, indent=2))
