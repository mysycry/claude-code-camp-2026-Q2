## Technical Goal

So what I wanted to build for Week 1 was a proper agent framework from scratch. Not using LangChain, not using any of those agent SDKs, just raw REST API calls to different LLM providers. The goal was to make something that can actually play the game — connect to CircleMUD, understand what the player sees, and let us talk to it naturally instead of typing weird game commands. The Ruby version is the original, but we also needed a Python port because that's what the team is more comfortable with for the later weeks. Everything had to be built one small piece at a time, thirteen steps total, each step adding one capability until we have a complete agent that can hold a conversation, call tools, remember context, and survive across multiple turns without exploding the token budget.

## Technical Uncertainty

To be honest, when I first looked at the Ruby code I was kind of overwhelmed. 

There are so many layers. config, registry, prompt builder, agent loop, logger, REPL, TUI, MCP host, context management 

and each one has its own class and its own file and they all reference each other. I was not sure if I could actually trace through how a single user message becomes an API call becomes a tool dispatch becomes a response. The Python port is supposed to match the Ruby structure but Andrew Brown made it clear that we have flexibility, we don't have to copy everything exactly. The thing I was unsure about was whether skipping steps would bite me later. Like if I just jump to step 12 without building the intermediate pieces, would I miss some important detail that the later layers depend on?

I was also worried about the MUD connection. The Ruby side uses MudManager which is a gem that handles the telnet protocol, ANSI stripping, session management, everything. But the Python side does not have MudManager. The Python agent communicates with the MUD through a Ruby daemon process — so there is a whole TCP bridge between Python and Ruby, and that is another thing that can break. If the daemon crashes or the port file gets stale, the entire agent just sits there timing out.

## Technical Observations

### The Step-by-Step Progression

The Ruby codebase has thirteen numbered directories from 00_config all the way to 12_context. 

Each one builds on the previous one. The progression goes like this. First we define the delta shapes like Tool, Message, and Context as plain structs (01_struct_skeleton). 

Then we build the Registry that maps tool names to actual functions and dispatches calls (02_the_registry). 

Then the Prompt Builder which formats messages into whatever JSON shape each LLM provider expects, and normalizes the responses back into one format (03_prompt_builder). 

Then the API Client which is just a raw HTTP caller with retry logic (04_api_client). 

Then the Agent loop itself — call LLM, check stop_reason, dispatch tools, repeat (05_agent_loop). 

Then the Logger writes structured JSONL events to disk so we can debug what happened (06_the_logger). 

The Run DSL wraps everything in a single .run command so we do not have to manually wire all the classes together (07_the_run_dsl). 

The REPL gives us an interactive terminal session (08_the_repl_loop). 

The Global Executable packages it as a gem so we can type boukensha anywhere (09_global_executable). 

Step 10 was originally the Standard Tool Library with FileSystem, Shell, and MUD tools but it got rewritten into an MCP host, meaning the agent gets its tools from external MCP servers now instead of built-in modules. 

Step 11 adds a full terminal UI using Charm's Bubble Tea framework. 

Step 12 adds context management with token tracking, compaction, and circuit breakers.

### The Python Port

The Python port lives in week1_baseline/python/ and follows the same step structure from 00_config through 12_context. 

But the Python version does not copy everything blindly. Some things we handled differently. The MUD tools in Python use a MudDaemonClient that talks to the Ruby daemon over TCP instead of using MudManager directly. 

The TUI in Python is a stub because Charm does not exist for Python, it falls back to the plain REPL. The context management, message structure, agent loop, logging, and configuration all follow the same patterns but written in idiomatic Python with dataclasses and with-blocks for the span lifecycle.

The final Python package at 12_context/boukensha/ is self-contained. It has about 20 files plus the tools subpackage. The main entry points are run() for one-shot tasks and repl() for interactive sessions. 

The Agent class does the core loop. The Context handles message history, token tracking, compaction, and memory injection. The memory.py adds SQLite-backed persistence for room exploration data. The tracer.py and opentelemetry.py add span-based observability that can export to Jaeger.

### The OpenCode Backend

The project uses OpenCode with **deepseek-v4-flash-free** as the default provider. This was added retroactively to every Ruby step that had backends. 

The backend just wraps the OpenCode REST API the same way the Anthropic, OpenAI, Gemini, and Ollama backends wrap theirs. Each backend normalizes the response into {stop_reason:, content:} so the agent loop never knows which provider it is talking to. 


### The MUD Daemon Bridge

This is probably the most fragile part of the whole setup. The Ruby mud_daemon.rb starts a TCP server on a random port and writes that port to a file in .mud_manager/port. 

The Python MudDaemonClient reads that file and sends JSON commands over TCP. Each command opens a new socket, sends the request, and closes. The daemon is single-threaded so it handles requests one at a time. The daemon also manages MUD sessions — when we connect, it opens a telnet connection to the actual MUD server, logs in, and keeps the session alive. 

When we send a command, the daemon drains any pending output, sends the command, and reads until the next prompt. This is slow because each command involves a full round trip through the daemon to the MUD and back.

### How the Agent Actually Runs

When we call boukensha.run(task), here is what happens. First it loads the config from .boukensha/settings.yaml, picks the provider and model, loads the system prompt, and resolves the MUD connection parameters. 

Then it creates a Context with those settings, a Registry with the tool definitions (FileSystem, Shell, MUD tools), a PromptBuilder for the chosen backend, a Client for HTTP calls, a Logger for JSONL output, and a Tracer for span observability. 

It adds the user task as a message and creates an Agent with all these components wired together. Agent.run() enters a loop. Each iteration checks if we hit max_iterations or max_turn_tokens. If not, it calls the LLM, parses the response, and either handles tool calls or returns the final text. 

Each tool call goes through the Registry.dispatch() which looks up the tool by name and calls its block function. The cycle continues until the LLM decides to respond directly.


## Technical Conclusions

After going through all thirteen steps and the Python port, I think the framework is solid for what it needs to do. The layered architecture makes sense — each piece has a single responsibility and we can swap out backends, tools, or the UI without touching the core loop. 

The Python port is faithful to the Ruby design but adapted to Python idioms and available libraries. The MCP approach in step 10 is actually clever because it means tools are external processes that can be written in any language, not just Ruby.

The fragile parts are the MUD daemon bridge and the port file mechanism. If the daemon crashes or the port file gets out of sync, the whole thing stops working. The session management in the daemon also needs work — stale sessions do not get cleaned up properly and cause reconnection timeouts. We had to add defensive disconnect-before-connect logic on both the reset script and the MUD tool registration to work around this.

The token compaction works but I am not sure the default threshold of 0.70 is right for all models. Deepseek V4 Flash has a 32K context window which is smaller than Claude's 200K, so compaction triggers more often. The 50% drop ratio also means we lose half our conversation history every compaction, which could affect the agent's ability to maintain coherent long-term behavior.

## Key Takeaway

Building an agent framework from scratch teaches things that using an SDK never will. We learn exactly where every token goes, how every tool call resolves, and why every timeout happens. 

One of the tradeoff is we spend a lot of time debugging infrastructure instead of building agent behavior. 

For a production system we would probably use an existing framework, but for understanding how agents actually work under the hood, this kind of deep dive is irreplaceable.

I have tried other courses like AWS Strands Agents, Google Agent Development Kit. But this course seems to be the MOST MEANINGFUL YET.