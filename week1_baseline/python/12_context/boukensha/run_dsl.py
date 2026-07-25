class RunDSL:
    def __init__(self, registry):
        self._registry = registry

    def tool(self, name, description="", parameters=None, block=None):
        return self._registry.tool(name, description=description, parameters=parameters, block=block)
