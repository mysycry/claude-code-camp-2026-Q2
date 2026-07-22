from boukensha.message import Message
from boukensha.tool import Tool


class Context:
    def __init__(self, task=None, system=None):
        self.task = task
        self.system = system
        self.messages: list[Message] = []
        self.tools: dict[str, Tool] = {}

    def register_tool(self, tool: Tool):
        self.tools[tool.name] = tool

    def add_message(self, role: str, content: str | None = None, tool_use_id: str | None = None):
        self.messages.append(Message(role=role, content=content, tool_use_id=tool_use_id))

    def clear_messages(self):
        self.messages.clear()

    @property
    def tool_count(self):
        return len(self.tools)

    @property
    def turn_count(self):
        return len(self.messages)

    def __repr__(self):
        task_name = getattr(self.task, "task_name", None) if self.task else None
        return f"<Context task={task_name} turns={self.turn_count} tools={self.tool_count}>"
