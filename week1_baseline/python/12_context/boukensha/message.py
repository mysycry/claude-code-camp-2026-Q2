from dataclasses import dataclass


@dataclass
class Message:
    role: str
    content: str | None = None
    tool_use_id: str | None = None

    def __repr__(self):
        tag = f" [{self.tool_use_id}]" if self.tool_use_id else ""
        content_preview = (self.content or "")[:60]
        return f"<Message role={self.role}{tag} content={content_preview}...>"
