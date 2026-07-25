from boukensha.errors import UnknownToolError
from boukensha.tool import Tool


class Registry:
    def __init__(self, context):
        self._context = context

    def tool(self, name, description="", parameters=None, block=None):
        if parameters is None:
            parameters = {}
        tool = Tool(name=str(name), description=description, parameters=parameters, block=block)
        self._context.register_tool(tool)
        return tool

    def dispatch(self, name, args=None):
        if args is None:
            args = {}
        tool = self._context.tools.get(str(name))
        if tool is None or tool.block is None:
            raise UnknownToolError(f"No tool registered as '{name}'")
        return tool.block(**args)
