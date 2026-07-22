import os

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
from boukensha.errors import ApiError, LoopError, UnknownToolError, UnsupportedModelError
from boukensha.logger import Logger
from boukensha.message import Message
from boukensha.prompt_builder import PromptBuilder
from boukensha.registry import Registry
from boukensha.run_dsl import RunDSL
from boukensha.tasks.base import Base as TaskBase
from boukensha.tasks.player import Player as TaskPlayer
from boukensha.tool import Tool

_boukensha_quiet = False
_boukensha_debug = False
_boukensha_config = None


def _get_config():
    global _boukensha_config
    if _boukensha_config is None:
        _boukensha_config = Config()
    return _boukensha_config


def quiet():
    global _boukensha_quiet
    _boukensha_quiet = True


def loud():
    global _boukensha_quiet
    _boukensha_quiet = False


def is_quiet():
    return _boukensha_quiet


def debug():
    global _boukensha_debug
    _boukensha_debug = True


def is_debug():
    return _boukensha_debug


_BACKEND_API_KEYS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "ollama_cloud": "OLLAMA_API_KEY",
    "opencode": "OPENCODE_API_KEY",
}

_BACKEND_CLASSES = {
    "anthropic": Anthropic,
    "openai": OpenAI,
    "gemini": Gemini,
    "ollama": Ollama,
    "ollama_cloud": OllamaCloud,
    "opencode": OpenCode,
}


def run(task, system=None, model=None, backend=None, api_key=None,
        ollama_host="http://localhost:11434", log=None, max_output_tokens=None, *, block=None):
    cfg = _get_config()
    task_class = TaskPlayer
    task_settings = cfg.tasks(task_class.task_name)

    if system is None:
        system = task_class.system_prompt(
            task_settings,
            user_prompts_dir=cfg.user_prompts_dir,
            default_prompts_dir=Config.PROMPTS_DIR,
        )
    if model is None:
        model = task_class.model(task_settings)
    if backend is None:
        backend = task_class.provider(task_settings)

    api_key = api_key or os.environ.get(_BACKEND_API_KEYS.get(backend, ""))

    ctx = Context(task=task_class, system=system)
    registry = Registry(ctx)

    if block is not None:
        block(RunDSL(registry))

    backend_cls = _BACKEND_CLASSES.get(backend)
    if backend_cls is None:
        raise ValueError(
            f"Unknown backend {backend!r}. Use {', '.join(sorted(_BACKEND_CLASSES))}."
        )

    if backend == "ollama":
        be = backend_cls(model=model, host=ollama_host)
    else:
        be = backend_cls(api_key=api_key, model=model)

    builder = PromptBuilder(ctx, be)
    client = Client(builder)
    effective_max_iterations = task_class.max_iterations(task_settings)
    effective_max_output_tokens = max_output_tokens or task_class.max_output_tokens(task_settings)
    logger = Logger(log=log, snapshot={
        "task": task_class.task_name,
        "max_iterations": effective_max_iterations,
        "max_output_tokens": effective_max_output_tokens,
        "model": model,
        "provider": backend,
    })
    agent = Agent(
        context=ctx, registry=registry, builder=builder, client=client, logger=logger,
        task_settings=task_settings, max_iterations=effective_max_iterations,
        max_output_tokens=effective_max_output_tokens,
    )

    ctx.add_message("user", task)

    try:
        return agent.run()
    finally:
        logger.close()


__all__ = [
    "Agent", "Anthropic", "Client", "Config", "Context", "Gemini", "Logger", "Message", "Ollama",
    "OllamaCloud", "OpenAI", "OpenCode", "PromptBuilder", "Registry", "RunDSL",
    "TaskBase", "TaskPlayer", "Tool", "ApiError", "LoopError", "UnknownToolError", "UnsupportedModelError",
    "quiet", "loud", "is_quiet", "debug", "is_debug", "run",
]
