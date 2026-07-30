import warnings

from boukensha.errors import UnknownToolError
from boukensha.tool import Tool


class Registry:
    def __init__(self, context, allow=None):
        self._context = context
        self._allow = allow

    def allowed(self, name, params=None):
        if self._allow is None:
            return True
        if "*" in self._allow:
            return True
        for rule in self._allow:
            if isinstance(rule, str):
                if rule == name:
                    return True
            elif isinstance(rule, dict):
                for tool_name, param_rules in rule.items():
                    if tool_name != name:
                        continue
                    if not params or not isinstance(param_rules, dict):
                        return True
                    for p, allowed_vals in param_rules.items():
                        if p in params:
                            val = params[p]
                            if isinstance(allowed_vals, (list, tuple)) and val not in allowed_vals:
                                return False
                    return True
        return False

    def tool(self, name, description="", parameters=None, block=None):
        if parameters is None:
            parameters = {}
        if not self.allowed(name):
            return None
        self._validate_rules(name, parameters)
        tool = Tool(name=str(name), description=description, parameters=parameters, block=block)
        self._context.register_tool(tool)
        return tool

    def _validate_rules(self, name, parameters):
        if self._allow is None:
            return
        for rule in self._allow:
            if isinstance(rule, dict) and name in rule:
                param_rules = rule[name]
                if isinstance(param_rules, dict):
                    for p in param_rules:
                        if p not in parameters:
                            warnings.warn(
                                f"Permission rule for '{name}' references "
                                f"non-existent parameter '{p}'"
                            )

    def dispatch(self, name, args=None):
        if args is None:
            args = {}
        if not self.allowed(name, args):
            raise UnknownToolError(f"Tool '{name}' is not permitted by allow rules")
        tool = self._context.tools.get(str(name))
        if tool is None or tool.block is None:
            raise UnknownToolError(f"No tool registered as '{name}'")
        return tool.block(**args)
