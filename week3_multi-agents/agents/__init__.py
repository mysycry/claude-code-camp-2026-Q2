"""
Boukensha Squad - a manager agent that orchestrates specialized sub-agents.

Each sub-agent handles one concern of playing and operating the MUD:
connection, map building, grinding, player reset, and observability
(Jaeger/Grafana). The manager is a Boukensha agent that decides which
sub-agent to call for a given task.
"""
