import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if "BOUKENSHA_DIR" not in os.environ:
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    os.environ["BOUKENSHA_DIR"] = os.path.join(repo_root, ".boukensha")

from boukensha.agent import Agent
from boukensha.backends.anthropic import Anthropic
from boukensha.backends.gemini import Gemini
from boukensha.backends.ollama import Ollama
from boukensha.backends.ollama_cloud import OllamaCloud
from boukensha.backends.opencode import OpenCode
from boukensha.backends.openai import OpenAI
from boukensha.client import Client
from boukensha.config import Config
from boukensha.context import Context
from boukensha.logger import Logger
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
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

ctx = Context(task=Player, system=system_prompt)
registry = Registry(ctx)

provider = Player.provider(player_settings)
model = Player.model(player_settings)

backend_map = {
    "anthropic": (Anthropic, "ANTHROPIC_API_KEY"),
    "gemini": (Gemini, "GEMINI_API_KEY"),
    "ollama": (Ollama, None),
    "ollama_cloud": (OllamaCloud, "OLLAMA_API_KEY"),
    "opencode": (OpenCode, "OPENCODE_API_KEY"),
    "openai": (OpenAI, "OPENAI_API_KEY"),
}

entry = backend_map.get(provider)
if entry is None:
    raise ValueError(f"Unsupported provider for player task: {provider}")

backend_cls, key_var = entry
if provider == "ollama":
    backend = backend_cls(model=model)
elif provider in ("anthropic", "gemini", "openai", "opencode", "ollama_cloud"):
    backend = backend_cls(api_key=os.environ[key_var], model=model)
else:
    raise ValueError(f"Unsupported provider for player task: {provider}")

builder = PromptBuilder(ctx, backend)
client = Client(builder)
logger = Logger()
agent = Agent(
    context=ctx,
    registry=registry,
    builder=builder,
    client=client,
    logger=logger,
    task_settings=player_settings,
)

registry.tool(
    "read_file",
    description="Read the contents of a file from disk",
    parameters={"path": {"type": "string", "description": "The file path to read"}},
    block=lambda path: open(os.path.normpath(os.path.join(base_dir, "..", "..", "ruby", "06_the_logger", path))).read(),
)

registry.tool(
    "list_directory",
    description="List the files in a directory",
    parameters={"path": {"type": "string", "description": "The directory path to list"}},
    block=lambda path: ", ".join(f for f in os.listdir(os.path.normpath(os.path.join(base_dir, "..", "..", "ruby", "06_the_logger", path))) if not f.startswith(".")),
)

ctx.add_message("user", "Read the README.md file and summarise what this MUD player assistant framework can do.")

print("=== BOUKENSHA Step 6: The Logger ===")
print()
print(f"Config: {config}")
print(f"Provider: {provider}")
print(f"Model: {model}")
print(f"Max iterations: {Player.max_iterations(player_settings)}")
print(f"Max output tokens: {Player.max_output_tokens(player_settings)}")
print()

result = agent.run()

print()
print("=== FINAL RESPONSE ===")
print(result)
