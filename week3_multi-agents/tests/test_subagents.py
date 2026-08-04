import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))

from agents.base import SubAgent, _subagent_block, register_subagents


class _EchoAgent(SubAgent):
    name = "echo_agent"
    description = "Echoes its args back."
    parameters = {
        "target": {"type": "string", "description": "Mob name."},
        "steps": {"type": "integer", "description": "Kill budget."},
    }

    def run(self, **kwargs):
        return f"echo:{kwargs.get('target')}|{kwargs.get('steps')}"


class _FakeRegistry:
    def __init__(self):
        self.tools = {}

    def tool(self, name, description="", parameters=None, block=None):
        self.tools[name] = {"parameters": parameters, "block": block}


class SubAgentBlockTestCase(unittest.TestCase):
    def test_block_forwards_typed_kwargs(self):
        agent = _EchoAgent()
        block = _subagent_block(agent)
        out = block(target="goblin", steps=5)
        self.assertEqual(out, "echo:goblin|5")

    def test_block_with_no_args(self):
        agent = _EchoAgent()
        block = _subagent_block(agent)
        self.assertEqual(block(), "echo:None|None")

    def test_register_binds_each_agent_individually(self):
        a1 = _EchoAgent()
        a1.name = "echo_one"
        a2 = _EchoAgent()
        a2.name = "echo_two"
        reg = _FakeRegistry()
        register_subagents(reg, [a1, a2])
        out_one = reg.tools["echo_one"]["block"](target="rat")
        out_two = reg.tools["echo_two"]["block"](target="goblin", steps=3)
        self.assertEqual(out_one, "echo:rat|None")
        self.assertEqual(out_two, "echo:goblin|3")


if __name__ == "__main__":
    unittest.main(verbosity=2)
