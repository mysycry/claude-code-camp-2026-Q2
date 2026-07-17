# Explore Agent Architectures

The largest confusion tech professionals have is applying the correct agent solution
because many solutions appear to overlap responsibilities. 

We will explore multiple agent architectures to determine fit for our agent workload.

## 1. An agent file with referenced files eg. AGENT.md,  @~/docs/*.MD

The simplest agent is creating an "agent file" and possibly importing other files that are read conditionally when needed.

We should attempt to create an agent file and see if it can connect to the MUD and complete a simple goal:
eg. "Find the bakery and list the menu."

We want to use the smallest and least intelligent model and scale up.

### Technical Observations

Using Deepseek V4 Flash we created an AGENTS.md with a simple prompt, and told it would need to manage its own local memory via simple markdown files. We provided it with the location of the MUD and the player's credentials.

The agent successfully connected to MUD.
The agent attempted to create temporary code files to manage a telnet connection and execute commands each time rather than maintaining a persistent session.


### Technical Conclusions

The agent could connect and execute commands but struggled with state persistence and goal decomposition. It treated each connection as a fresh start rather than maintaining a coherent session. It spent too much effort writing temporary scaffolding code instead of leveraging the existing MUD script.

For coding tasks, use provided coding harnesses. For specialized game agents, build a custom loop with persistent connections and proper telnet handling rather than generating new scripts each time.

> Use coding harnesses for coding, and for specialized agents make your own loop.

## 2. Agent Skills driven by main agent eg. ~/.skills

A skill is a reusable knowledge package that teaches an agent how to perform a specific task. Skills live in a `.skills/` directory and are loaded on-demand by the main agent.

### Technical Observations

Using the official opencode creator skill to create our skill, it was successful in creating a skill that could reliably connect and play the MUD using Deepseek V4 Flash.

It was able to complete simple goals despite many calls, and it stopped when given a task that was not possible. For example, when we asked it to practice kick at the guild, it found the correct guild and reported it had no more kicks it could perform. But it never considered if it should attempt to level up or how hard it would be to level kick one more level.

When giving it the broader task to defeat the massive minotaur in the newbie zone, it found the newbie zone but did a considerable amount of backtracking first trying to find the minotaur and when it couldn't find it, it gave up. It was never able to open any locked doors.

Even telling the agent it was in the "Red Room" it was single-focused on finding that room and doing nothing else.

A real player would have held the goal and been more productive, expecting it to be the boss of the level, and progressively leveling up and exploring rather than simply trying to find the end boss.

It did appear to update the world and player state but not in real time, which makes it hard to observe what it knows has changed. It should have been collecting observations to explore later, but instead it would go back and brute force, not appearing to reason about its journey pathing.

I could see it having a difficult time managing the state of just markdown files for memory if they grew too large.
I think we need dynamic adaptive task management:

eg. Goal: Defeat the Massive Minotaur in the Newbie Zone north of town

Before I find the Newbie Zone and leave the town, do I need to prepare?
- collect information from NPCs for my goal?
- can I obtain any resources?
- any training I need to do?

I should find the Newbie Zone.
- while on path was there anything of interest that should warrant a detour? Would this spawn a sidequest?
- Explorer Mode:
  - Focused: Stay on main quest
  - Curious: Consider sidequests while on main quest, especially if it could save backtracking or provide an advantage or resources
  - Aloof: Do all sidequests, and not worry too quickly about main quest progression

I have found the Newbie Zone.
- Risk Mode:
  - Bold: Try and push exploration to find your end goal, and try to run past high level mobs, or run away, try and push fighting stronger mobs to level up faster, and take more risks
  - Balanced: Progress through areas where mobs are at or slightly above your level. Retreat and heal when HP drops below half. Return to town only when necessary for supplies
  - Scared: Don't progress exploration where mobs are higher level or I am at risk of dying. Take the time to be in a safe area and heal. If hungry and thirsty or at risk of losing money, backtrack to town always, have plenty of resources
    - There can be high level mobs that are not a risk like Town guards, context is key, if we are in a forest of monsters then mobs are higher risk. 

### Technical Conclusions (Section 2)

Agent Skills does work, and quite well, but we will need much more complex state, world and player management.
We really need to have auditable visibility of the agent for reporting token usage and to review the player journey. We need a custom agentic loop. We want an agent that acts, and spends less time asking "What should it do".

We should probably be defining a Player Persona, which describes how the player likes to play, based on a mix of modes eg: Risk Mode, Exploration Mode etc.

When we enter a goal we should see goal decomposition/planning so we can observe how it will reason about the goal.