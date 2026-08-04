## Technical Goal

So for Week 3, the goal was to take the single agent from Week 2 and turn it into a proper multi-agent squad. One manager agent that decides what to do, and then a set of sub-agents that each handle one specific thing. The idea being that instead of one big agent trying to do everything inside a single loop, you have specialists. The manager reads the task, picks which sub-agent handles it, and the sub-agent does the actual work and reports back. Along with that, I wanted a live player status dashboard in Grafana. Like a bulletin board that shows the current state of the player character while the squad is running. Level, gold, XP, where the character is right now, the last monster it killed, where it's headed, and a feed of recent events. Something you can just leave open on a second monitor and watch the squad work.

## Technical Uncertainty

The things I was not sure about going in. First, I was not sure how the sub-agents would actually get wired into the existing agent loop. The Boukensha framework from Week 2 has a Registry that maps tool names to functions, and the agent calls tools by name. The question was whether a sub-agent is a tool, or something else. Because a tool in this framework is just a block function that takes arguments and returns a string. But a sub-agent needs to connect to the MUD, move around, fight, and come back. That is a lot more stateful than a normal tool. So there was real doubt about whether the whole squad thing would fit the framework or whether we would have to fight the framework to make it work.

Second, I was worried about the dashboard. The Grafana setup uses the Infinity datasource to query a local memory HTTP server. In Week 2 the queries were pretty simple. But this time I wanted string values on the board. Things like the room name and the last kill. And from past experience, string values in stat panels are where things get weird. Grafana wants numbers in some places, and if the datasource returns a flat object instead of an array, the panel just shows nothing.

Third, the grinding. Week 2 left us with a grind agent that kept reporting zero kills even when the character was clearly fighting. I genuinely did not know if that was a parsing problem, a combat detection problem, or a navigation problem. Could be all three. And on top of that, the game resets kept dropping the character in random places instead of the requested room, and movement points regenerate so slowly that a full exploration run could take ten minutes just walking.

## Technical Observations

### The Multi-Agent Squad

The whole thing lives in `week3_multi-agents/agents/`. The manager is `squad.py`. It reads the config, builds the system prompt, and calls `boukensha.run()` with a block that registers all the sub-agents. Each sub-agent extends a `SubAgent` base class that gives it a `_summary()` helper so every agent returns a consistent result format.

The manager does not have its own behavior really. It just decides which sub-agent to call and passes along the task. The system prompt in `system.md` tells it to pick the right sub-agent for the request, and if the request is vague, run the observability and connection checks first before doing anything else.

Here are the sub-agents and what each one is for:

- **`connection_agent`** — Checks that the MUD daemon is running, the MUD server is reachable, and the player can actually log in. Reads the port file from `.mud_manager`, pings the daemon, then tries a real login. This is the one to call first when anything MUD related looks broken.
- **`reset_agent`** — Moves the player to a start room using the admin account. Loads `player_reset.py`, connects as the admin character, does a `goto` and then a `transfer` to pull the player character to wherever the admin is standing.
- **`map_agent`** — Explores the MUD from the current room using a depth-first search with backtracking. Builds a room graph and caches it to `rooms_cache.json`. It also reports the best hunting spots, which are the rooms with the most monsters. When it's done it posts a snapshot to the bulletin board with the explored room count and the best spot it found.
- **`grind_agent`** — The fighter. Explores the area looking for monsters and kills them for XP and gold. It takes a target mob name and a kill budget. Manages its own HP and movement recovery, loots corpses after a kill, and posts the final score to the bulletin board.
- **`observability_agent`** — Checks the whole observability stack. Jaeger OTLP receiver, Jaeger UI and services API, Grafana API and UI, and whether the docker compose containers are actually up. Returns one check row per component.
- **`grafana_agent`** — Checks that Grafana has the Jaeger datasource provisioned and that the dashboard JSON files exist on disk.
- **`trace_agent`** — Sends a synthetic test span through the OTLP pipeline using the Boukensha tracer, then checks the Jaeger services API to prove the span actually landed.

The registry wiring was the surprise here. It turns out a sub-agent works perfectly fine as a normal tool. `SubAgent` has a `run()` method, and the registration wraps it so the registry can dispatch to it by name. The manager just calls the sub-agent by its name the same way it would call any other tool. So the framework did not need any changes. That was a relief honestly.

### The Bulletin Board

The bulletin board is a shared SQLite store. The agents write to it, and a memory HTTP server serves it to Grafana. It lives in `week3_multi-agents/agents/bulletin.py`.

The store has two tables. `player_state` is a key-value table that holds the latest snapshot. `player_events` is an append-only log of events. The `post_player_snapshot()` helper is the main write path. It takes the parsed score, the current location, the last kill, a destination, and an optional note. It writes all the score fields prefixed with `score_`, computes percentages for HP, mana, movement, and XP progress and writes those as `pct_*`, then logs the kill and navigation events and sets an `updated_at` timestamp.

The memory HTTP server is `week3_multi-agents/memory/memory_server.py` on port 9876. I added two endpoints. `/player-state` returns the whole `player_state` table as a flat JSON object with numeric coercion, so values that look like numbers become actual numbers. `/player-events?limit=N` returns the recent events as an array of objects with timestamp, kind, and message.

Then the Grafana dashboard. It's `week3_multi-agents/grafana/dashboards-json/bulletin-board.json`, titled Boukensha Bulletin Board. It uses the Infinity datasource pointed at `host.docker.internal:9876`. The layout is five stat cards at the top for Level, Gold, Experience, XP to Next Level, and Last Kill. Below that four gauges for Health, Mana, Movement, and XP Progress, each using the percentage fields with color thresholds. Then Current Location and Destination as wide stat panels. And at the bottom a Recent Player Events table fed by `/player-events`.

### Problem 1: The grind agent kept reporting zero kills

This was the one that took the longest to figure out. The character was clearly fighting and winning. We proved it manually. XP was going up after kills. But the grind agent always reported 0 kills. There were actually two bugs hiding here.

The first bug was in `_mob_alias()`. The function turns an entity line like "A goblin is standing here." into a kill target. The old code stripped leading articles with a regex, but the pattern was wrong. It would keep the word "a" in some cases, so the alias came out as "a goblin" and the `kill` command failed because the game does not match on leading articles.

The second bug was in `_fight()`. After you issue `kill <mob>`, the game changes the mob's line in the room to something like "The Pawn of the Black Court is here, fighting YOU!". The old code checked whether the original entity string was still in the room. But it was never there during combat, because the line changed. So the agent thought the fight was already over, declared a kill before it happened, and moved on. Zero real kills, but a bunch of fights started and abandoned.

The fix for the alias was to split on the standing verbs, strip articles from the word list, and then take the first three clean words. The fix for `_fight` was to stop looking for the original string. Instead, after each tick we check if any entity still contains the word "fighting", and separately check if the first word of the alias still appears in any entity line. If neither is true, the mob is actually gone, meaning it's dead. That made the kill detection real.

### Problem 2: The dashboard showed redundant text and clipped titles

I made the mistake of setting `textMode: "value_and_name"` on the string panels. That sounds fine in theory but in practice the stat panel then shows the field name next to the value. So instead of seeing just "pawn" you see "last_kill" and "pawn" on top of each other, which looks broken. The user flagged this immediately. Same for location and destination.

The other complaint was that the panel title was only showing two or three letters, and there were empty gaps in the layout.

The fix was to go back to `textMode: "value"` so the panel only renders the value, and switch `colorMode` to `background` so the whole panel is a solid colored card. That way the value is big and readable, the title sits on top, and nothing redundant shows. The layout was also adjusted so the rows sum to the full 24 unit width with no gaps. Then I bumped the dashboard version and restarted the Grafana container, because the file-based provisioner reads the dashboards at startup and does not pick up changes on its own.

### Problem 3: The gold was showing as zero

When I first saw gold = 0 with a currency unit on the dashboard, I thought it was a panel bug. It turned out to be real game state. The character died during a test run. We had moved the character while it was at 4 HP and then it tried to fight something it should not have, a kind soul NPC in a donation room, and died. On death the character dropped all its gold and equipment with the corpse, and the corpse despawned before anyone looted it. XP also dropped from 19206 to 11543.

There is no way to just give the character gold either. The account is a normal player in tbaMUD, not an immortal, so the admin commands like set and give are not available. The only way to get the gold back is to actually grind and loot. So the dashboard was telling the truth. Lesson: when a number on the dashboard looks wrong, check the game first.

### Problem 4: The reset drops the character in random places

The reset agent uses `goto <vnum>` and then `transfer` to pull the player. But the live server does not map the vnums the way the offline world database does. Resetting to the newbie zone vnum dropped the character in a big outdoor field instead. The field is called "The Great Field Of Midgaard" and there are many rooms with that exact same name. Since the DFS keys visited rooms by name and exit signature, all those identical rooms collapsed into one node and the search basically stopped. The grind and map agents would burn their whole budget crossing the field and never reach real monsters.

The fix for the visited set was to key rooms by both name and the exit signature, so identical names with different exits stay distinct. That helped the map agent. But the field is still a problem because crossing it takes a long time with movement recovery. This one is still not fully solved. It needs either a smarter start location or a better reset.

### Problem 5: Movement recovery is brutally slow

Movement points regenerate on a tick. Every time the character runs out of movement, the agent has to sleep and wait, and each sleep cycle takes about 18 to 20 seconds for a small regen. A grind run with a budget of 20 rooms could take 400 to 600 seconds, which blew past every timeout we set. We managed it by setting smaller room budgets and sleeping between moves, but it is the main reason the squad feels slow in practice.

### Problem 6: Jaeger showing no trace results

The user opened Jaeger and the trace search came back empty. But the Jaeger API clearly had traces for the `boukensha` service, including some from the same morning. The issue was the time range in the UI. The default lookback is the last hour, and the most recent trace was over three hours old because nobody had run the squad recently. Switching the lookback to the last 24 hours showed everything. So the traces were never missing, the window was just too small.

### Problem 7: The log viewer showing no sessions

Same kind of story. The user opened the Boukensha Log Viewer on port 4567 and saw no sessions. But the viewer was actually listing 109 sessions when we queried it. The newest one was from the last `run_squad` call. The reason it looked empty is that all the ad-hoc Python test scripts we had been running directly bypass the squad logger entirely, so they never wrote session files. Sessions only get written when something goes through `boukensha.run()`. If you want a session to appear, you have to run through the squad entrypoint.

## Technical Conclusions

The multi-agent squad works. The key realization was that a sub-agent is just a tool as far as the framework is concerned. No changes to the core loop were needed. The manager decides which specialist to call and the sub-agents do the work. That is a much cleaner split than what we had in Week 2, where one agent tried to do everything.

The bulletin board dashboard works too. The data pipeline is bulletin module to SQLite to memory server to Infinity datasource to Grafana. We verified it end to end by posting a fresh snapshot and watching the values appear through every layer. The string panels are the trickiest part of Grafana, and the combination of `textMode: value` with `colorMode: background` is what finally made them look right.

The remaining problems are mostly game-level, not framework-level. The reset dropping the character in the middle of a huge field, and the painfully slow movement regen, are what make grinding slow and unreliable. If I had more time I would fix the reset to put the character somewhere actually useful, and probably pre-plan a route to the zone instead of letting the DFS discover it room by room.

There is also a question we looked at about whether to rewrite this whole flow using the AWS Strands Agents SDK. Strands is open source and Apache licensed, and it can run fully local with Ollama. It also emits OpenTelemetry natively, so it would drop straight into the existing Jaeger and Grafana stack. The mapping would be the manager becomes a Strands graph or agents-as-tools pattern, and the MUD helpers become Strands tools with minimal rewriting since they are already plain Python. But it is a model-driven framework, meaning the LLM decides the orchestration instead of the code, so the deterministic grind and map logic would need to live in a Strands graph to keep it predictable. We did not build it, just talked through the design.

## Key Takeaway

A multi-agent system does not need a fancy new framework, the existing tool registry handles it fine, but the real bottleneck is the game world itself with its slow regen and unreliable resets, so agent reliability depends more on the environment than on the orchestration code.
