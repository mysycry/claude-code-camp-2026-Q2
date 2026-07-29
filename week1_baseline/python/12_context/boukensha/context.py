import os

from boukensha.models import DEFAULT_CONTEXT_WINDOW
from boukensha.tool import Tool
from boukensha.message import Message


class Context:
    def __init__(self, system=None, context_window=DEFAULT_CONTEXT_WINDOW,
                 working_dir=None, compaction_threshold=0.70,
                 memory_store=None):
        self.system = system or ""
        self.context_window = context_window
        self.compaction_threshold = compaction_threshold
        self.working_dir = os.path.abspath(working_dir) if working_dir else None
        self.messages = []
        self.tools = {}
        self.current_tokens = 0
        self.turn_tokens = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.compaction_count = 0
        self.tokens_recovered = 0
        self.memory_store = memory_store
        self._injected_here = False

    def register_tool(self, tool):
        self.tools[tool.name] = tool

    def add_message(self, role, content, tool_use_id=None):
        self.messages.append(Message(role, content, tool_use_id))

    def inject_here_block(self):
        if not self.memory_store:
            return False
        block = self.memory_store.here_block()
        if not block:
            return False
        if self._injected_here:
            lines = self.system.split('\n')
            lines = [l for l in lines if not l.strip().startswith('[here]') and not l.strip().startswith('[frontier]') and not l.strip().startswith('[explored]')]
            self.system = '\n'.join(lines).rstrip()
        self.system = self.system.rstrip() + "\n\n" + block
        self._injected_here = True
        return True

    def update_tokens(self, n):
        self.current_tokens = int(n) if n else 0

    def reset_turn_tokens(self):
        self.turn_tokens = 0

    def add_turn_tokens(self, input_tokens, output_tokens):
        inp = int(input_tokens or 0)
        out = int(output_tokens or 0)
        self.turn_tokens += inp + out
        self.total_input_tokens += inp
        self.total_output_tokens += out

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

    def compact_messages(self, target_fraction=0.50):
        if len(self.messages) < 4:
            return 0
        drop_count = max(
            min(
                int((len(self.messages) - 2) * 0.50 + 0.5),
                len(self.messages) - 3,
            ),
            0,
        )
        if drop_count <= 0:
            return 0
        kept = [self.messages[0]]
        kept.extend(self.messages[drop_count + 1:])
        dropped_msgs = self.messages[1:drop_count + 1]
        self.messages = kept
        self.current_tokens = 0
        self.compaction_count += 1
        self.tokens_recovered += sum(
            m.token_estimate() for m in dropped_msgs
        )
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

    def summary(self):
        return {
            "window": self.context_window,
            "current": self.current_tokens,
            "pct": self.usage_pct(),
            "total_in": self.total_input_tokens,
            "total_out": self.total_output_tokens,
            "turn_tokens": self.turn_tokens,
            "compactions": self.compaction_count,
            "tokens_recovered": self.tokens_recovered,
        }

    def __repr__(self):
        return (
            f"<Context turns={self.turn_count} tools={self.tool_count} "
            f"window={self.context_window} current={self.current_tokens} "
            f"compactions={self.compaction_count}>"
        )
