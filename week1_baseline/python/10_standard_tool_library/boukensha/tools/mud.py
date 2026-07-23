import warnings


class Mud:
    _warned = False

    @classmethod
    def register(cls, registry, host="localhost", port=4000, name=None, password=None):
        if not cls._warned:
            warnings.warn("MUD tools not available: mud_manager is not implemented in Python")
            cls._warned = True
