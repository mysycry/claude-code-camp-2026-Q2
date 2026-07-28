# Goal: Benchmark navigation cost to expose why the agent could not reliably reach the bakery

- Ran repeated start-to-bakery navigation sessions.
- Observed runs consuming roughly 65K tokens without reaching the destination.
- Identified missing exit knowledge, repeated room reasoning, and manual resets.
- Used those failures to drive automated resets and structured room inspection.
