import os
import socket
import sys

from boukensha.agent import Agent
from boukensha.errors import ApiError, LoopError


PROMPT = "boukensha> "

HELP = """\
Commands:
  /clear   wipe conversation history (tools stay)
  /exit    leave the REPL
  /help    show this message"""


class Repl:
    def __init__(self, context=None, registry=None, builder=None, client=None, logger=None,
                 config_dir=None, provider=None, model=None, version=None, api_key=None,
                 task_settings=None, max_iterations=None, max_output_tokens=None, mud=None):
        self.context = context
        self.registry = registry
        self.builder = builder
        self.client = client
        self.logger = logger
        self.task_settings = task_settings
        self.max_iterations = max_iterations
        self.max_output_tokens = max_output_tokens
        self.config_dir = config_dir
        self.provider = provider
        self.model = model
        self.version = version
        self.api_key = api_key
        self.mud = mud
        self.turn = 0
        self._output_cb = None

    def on_output(self, callback):
        self._output_cb = callback

    def banner(self):
        key_status = "\u2717 API key not set"
        if self.api_key and self.api_key.strip():
            key_status = "\u2713 API key set"
        provider_line = f"{self.provider or 'default'} ({self.model or 'default'})  {key_status}"
        config_exists = self.config_dir and os.path.isdir(self.config_dir)
        if config_exists:
            config_line = self.config_dir
        else:
            config_line = f"{self.config_dir or '(default)'}  \u2717 directory not found"
        ver = self.version or "?.?.?"

        mud_status = self._mud_status_string()

        return f"""
\u2554\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2557
\u2551  BOUKENSHA MUD Assistant (v{ver}){' ' * max(0, 9 - len(ver))}\u2551
\u255a\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u2550\u255d
  config:    {config_line}
  provider:  {provider_line}
  mud:       {mud_status}

  /clear           reset conversation history
  /exit or /quit    leave the REPL

"""

    def handle_command(self, input_text):
        if input_text in ("/exit", "/quit"):
            self._output("Goodbye.")
            return "quit"
        elif input_text == "/help":
            self._output(HELP)
            return "command"
        elif input_text == "/clear":
            self.context.clear_messages()
            self.turn = 0
            self._output("(conversation history cleared)")
            return "command"
        return None

    def run_turn(self, input_text):
        self.turn += 1
        self.logger.turn(n=self.turn)

        self.context.add_message("user", input_text)

        agent = Agent(
            context=self.context,
            registry=self.registry,
            builder=self.builder,
            client=self.client,
            logger=self.logger,
            task_settings=self.task_settings,
            max_iterations=self.max_iterations,
            max_output_tokens=self.max_output_tokens,
        )
        try:
            result = agent.run()
            self._output("")
            self._output(result)
        except LoopError as e:
            self._output(f"\n[error] {e}")
        except ApiError as e:
            self._output(f"\n[error] API call failed: {e}")

    def start(self):
        self._output(self.banner())
        while True:
            if not self._output_cb:
                print(PROMPT, end="", flush=True)

            try:
                line = sys.stdin.readline()
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                break
            input_text = line.strip()
            if not input_text:
                continue

            result = self.handle_command(input_text)
            if result == "quit":
                break
            if result:
                continue

            self.run_turn(input_text)

    def _mud_status_string(self):
        if not self.mud:
            return "(not configured)"
        host = self.mud.get("host") or "localhost"
        port = self.mud.get("port") or 4000
        name = self.mud.get("name")

        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3)
            s.connect((host, port))
            s.close()
        except Exception:
            return f"{host}:{port}  \u2717 not reachable"

        reachable = "\u2713" if name and name.strip() else "\u2713"
        return f"{reachable} {host}:{port}"

    def _output(self, text):
        if self._output_cb:
            self._output_cb(str(text))
        else:
            print(text)
