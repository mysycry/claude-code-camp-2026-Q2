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


__all__ = [
    "Agent", "Anthropic", "Client", "Config", "Context", "Gemini", "Logger", "Message", "Ollama",
    "OllamaCloud", "OpenAI", "OpenCode", "PromptBuilder", "Registry",
    "TaskBase", "TaskPlayer", "Tool", "ApiError", "LoopError", "UnknownToolError", "UnsupportedModelError",
    "quiet", "loud", "is_quiet", "debug", "is_debug",
]
