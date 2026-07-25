import os

from boukensha.models import DEFAULT_CONTEXT_WINDOW
from boukensha.tool import Tool
from boukensha.message import Message


class Context:
    def __init__(self, system=None, context_window=DEFAULT_CONTEXT_WINDOW,
                 working_dir=None, compaction_threshold=0.85):
        self.system = system or ""
        self.context_window = context_window
        self.compaction_threshold = compaction_threshold
        self.working_dir = os.path.abspath(working_dir) if working_dir else None
        self.messages = []
        self.tools = {}
        self.current_tokens = 0
        self.turn_tokens = 0

    def register_tool(self, tool):
        self.tools[tool.name] = tool

    def add_message(self, role, content, tool_use_id=None):
        self.messages.append(Message(role, content, tool_use_id))

    def update_tokens(self, n):
        self.current_tokens = int(n) if n else 0

    def reset_turn_tokens(self):
        self.turn_tokens = 0

    def add_turn_tokens(self, input_tokens, output_tokens):
        self.turn_tokens += int(input_tokens or 0) + int(output_tokens or 0)

    def usage_fraction(self):
        if self.context_window > 0:
            return self.current_tokens / self.context_window
        return 0.0

    def usage_pct(self):
        return round(self.usage_fraction() * 100)

    def needs_compaction(self, threshold=None):
        if threshold is None:
            threshold = self.compaction_threshold
        return self.usage_fraction() >= threshold

    def compact_messages(self, target_fraction=0.60):
        drop_count = max(
            min(
                int(len(self.messages) * 0.40 + 0.5),  # ceil via float+int
                len(self.messages) - 2,
            ),
            0,
        )
        self.messages = self.messages[drop_count:]
        self.current_tokens = 0
        return drop_count

    def clear_messages(self):
        self.messages = []
        self.current_tokens = 0

    @property
    def tool_count(self):
        return len(self.tools)

    @property
    def turn_count(self):
        return len(self.messages)

    def __repr__(self):
        return (
            f"<Context turns={self.turn_count} tools={self.tool_count} "
            f"window={self.context_window} current={self.current_tokens}>"
        )
