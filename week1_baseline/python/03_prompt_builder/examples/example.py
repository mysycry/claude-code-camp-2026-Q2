import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if "BOUKENSHA_DIR" not in os.environ:
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    os.environ["BOUKENSHA_DIR"] = os.path.join(repo_root, ".boukensha")

from boukensha.backends.anthropic import Anthropic
from boukensha.backends.gemini import Gemini
from boukensha.backends.ollama import Ollama
from boukensha.backends.ollama_cloud import OllamaCloud
from boukensha.backends.opencode import OpenCode
from boukensha.backends.openai import OpenAI
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
    "look",
    description="Look around the current room for details",
    parameters={},
    block=lambda: "A damp stone corridor stretches north. Torches flicker on the walls.",
)

registry.tool(
    "move",
    description="Move the player in a direction (north, south, east, west, up, down)",
    parameters={"direction": {"type": "string", "description": "The direction to move"}},
    block=lambda direction: f"You move {direction} into a torch-lit corridor.",
)

ctx.add_message("user", "I just arrived in the dungeon. What's around me, and can you move north?")
ctx.add_message("assistant", "Let me take a look around first.")
ctx.add_message("tool_result", "A damp stone corridor stretches north. Torches flicker on the walls.", tool_use_id="toolu_01X")

print("=== BOUKENSHA Step 3: Prompt Builder ===")
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

print()
print(f"Config: {config}")
print(f"Provider: {provider}")
print(f"Model: {model}")
print(json.dumps(builder.to_api_payload(), indent=2))
