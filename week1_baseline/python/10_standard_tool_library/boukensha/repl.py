import os
import socket
import sys

from boukensha.agent import Agent
from boukensha.errors import ApiError, LoopError


PROMPT = "boukensha> "

HELP = """\
Commands:
  /quiet   suppress logging output
  /loud    re-enable logging output
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

    def start(self):
        print(self._banner())

        while True:
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

            if input_text in ("/exit", "/quit"):
                print("Goodbye.")
                break
            elif input_text == "/help":
                print(HELP)
                continue
            elif input_text == "/quiet":
                import boukensha
                boukensha.quiet()
                print("(logging suppressed — type /loud to re-enable)")
                continue
            elif input_text == "/loud":
                import boukensha
                boukensha.loud()
                print("(logging enabled)")
                continue
            elif input_text == "/clear":
                self.context.clear_messages()
                self.turn = 0
                print("(conversation history cleared)")
                continue

            self._run_turn(input_text)

    def _banner(self):
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

  /quiet or /loud   toggle logging
  /clear           reset conversation history
  /exit or /quit    leave the REPL

"""

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

    def _run_turn(self, input_text):
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
            print()
            print(result)
        except LoopError as e:
            print(f"\n[error] {e}")
        except ApiError as e:
            print(f"\n[error] API call failed: {e}")
