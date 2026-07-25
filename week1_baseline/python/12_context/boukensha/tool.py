from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict = field(default_factory=dict)
    block: Callable[..., Any] | None = None

    def __repr__(self):
        desc = (self.description or "")[:40]
        keys = list(self.parameters.keys()) if self.parameters else []
        return f"<Tool name={self.name} description={desc} params={keys}>"
