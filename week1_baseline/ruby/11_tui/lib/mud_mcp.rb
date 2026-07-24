require "json"
require "mud_manager"

module MudMcp
  PROTOCOL_VERSION = "2025-03-26"

  class Server
    def initialize(
      host: ENV.fetch("MUD_HOST", "localhost"),
      port: ENV.fetch("MUD_PORT", "4000").to_i,
      username: ENV["MUD_USERNAME"],
      password: ENV["MUD_PASSWORD"]
    )
      @host     = host
      @port     = port
      @username = username
      @password = password
      @session  = nil
      @p        = MudManager::Primitives
      @running  = false
    end

    def start
      @running = true
      send_event("MCP server started: MudManager #{MudManager::VERSION rescue "0.1.0"}")
      handle_messages
    end

    private

    def handle_messages
      $stdin.each_line do |line|
        begin
          msg = JSON.parse(line)
          dispatch(msg)
        rescue JSON::ParserError
          send_error(nil, -32700, "Parse error: invalid JSON")
        rescue StandardError => e
          send_error(nil, -32603, "Internal error: #{e.message}")
        end
      end
    rescue IOError
      # stdin closed — shutdown
    end

    def dispatch(msg)
      id     = msg["id"]
      method = msg["method"]
      params = msg["params"] || {}

      case method
      when "initialize"
        handle_initialize(id, params)
      when "notifications/initialized"
        handle_initialized
      when "notifications/exit"
        @running = false
      when "tools/list"
        handle_tools_list(id, params)
      when "tools/call"
        handle_tools_call(id, params)
      else
        send_error(id, -32601, "Method not found: #{method}")
      end
    end

    # ── Initialize ──────────────────────────────────────────────

    def handle_initialize(id, params)
      unless params["protocolVersion"] == PROTOCOL_VERSION
        send_event("client requested protocol #{params["protocolVersion"].inspect}, using #{PROTOCOL_VERSION}")
      end

      send_result(id, {
        protocolVersion: PROTOCOL_VERSION,
        capabilities: {
          tools: {}
        },
        serverInfo: {
          name: "mud_manager",
          version: "0.1.0"
        }
      })

      auto_connect
    end

    def handle_initialized
      send_event("client initialized")
    end

    # ── tools/list ──────────────────────────────────────────────

    TOOL_DEFINITIONS = [
      {
        name: "mud_connect",
        description: "Open the connection to the MUD server and log in with the configured " \
                     "character name and password. Safe to call when already connected " \
                     "(returns current status instead of reconnecting).",
        inputSchema: {
          type: "object",
          properties: {},
          required: []
        }
      },
      {
        name: "mud_disconnect",
        description: "Close the connection to the MUD server gracefully.",
        inputSchema: {
          type: "object",
          properties: {},
          required: []
        }
      },
      {
        name: "mud_status",
        description: "Return whether the MUD session is currently connected.",
        inputSchema: {
          type: "object",
          properties: {},
          required: []
        }
      },
      {
        name: "look",
        description: "Look at the current room or at a specific target. " \
                     "Call with NO arguments to describe the current room. " \
                     "Pass a target to inspect a specific item, mob, or player. " \
                     "Use preposition 'in' to look inside a container, 'at' to inspect something, " \
                     "or a direction (north/east/south/west/up/down) to peek into an adjacent room.",
        inputSchema: {
          type: "object",
          properties: {
            target:      { type: "string", description: "Item, mob, or player name to inspect" },
            preposition: { type: "string", description: "Preposition: in, at, north, east, south, west, up, down" }
          },
          required: []
        }
      },
      {
        name: "examine",
        description: "Examine a target in detail (more verbose than look).",
        inputSchema: {
          type: "object",
          properties: {
            target: { type: "string", description: "The item, mob, or player to examine" }
          },
          required: ["target"]
        }
      },
      {
        name: "check",
        description: "Query information about your character or surroundings. " \
                     "Kinds: score, inventory, equipment, gold, exits, time, weather, " \
                     "levels, wimpy, toggle, where.",
        inputSchema: {
          type: "object",
          properties: {
            kind: { type: "string", description: "What to check: score | inventory | equipment | gold | exits | time | weather | levels | wimpy | toggle | where" }
          },
          required: ["kind"]
        }
      },
      {
        name: "move",
        description: "Move in a compass direction or up/down.",
        inputSchema: {
          type: "object",
          properties: {
            direction: { type: "string", description: "Direction: north | east | south | west | up | down" }
          },
          required: ["direction"]
        }
      },
      {
        name: "flee",
        description: "Attempt to flee from combat in a random available direction.",
        inputSchema: {
          type: "object",
          properties: {},
          required: []
        }
      },
      {
        name: "set_position",
        description: "Change body position. Use 'rest' or 'sleep' between fights to recover " \
                     "HP and mana. Must be standing to move or fight.",
        inputSchema: {
          type: "object",
          properties: {
            position: { type: "string", description: "Position: stand | sit | rest | sleep | wake" }
          },
          required: ["position"]
        }
      },
      {
        name: "track",
        description: "Attempt to track a mob or player by name, revealing which direction " \
                     "they are in. Requires the Track skill.",
        inputSchema: {
          type: "object",
          properties: {
            target: { type: "string", description: "Name of the mob or player to track" }
          },
          required: ["target"]
        }
      },
      {
        name: "attack",
        description: "Attack a target. Style 'kill' is the standard approach; " \
                     "'murder' bypasses the mercy check; 'hit' is a one-off strike.",
        inputSchema: {
          type: "object",
          properties: {
            target: { type: "string", description: "Name of the mob or player to attack" },
            style:  { type: "string", description: "Attack style: kill | hit | murder (default: kill)" }
          },
          required: ["target"]
        }
      },
      {
        name: "skill_strike",
        description: "Use a combat skill against a target.",
        inputSchema: {
          type: "object",
          properties: {
            skill:  { type: "string", description: "Skill: bash | kick | backstab | rescue | assist" },
            target: { type: "string", description: "Name of the mob or player" }
          },
          required: ["skill", "target"]
        }
      },
      {
        name: "consider",
        description: "Assess a mob's relative strength before engaging in combat. " \
                     "Always consider before attacking an unknown mob.",
        inputSchema: {
          type: "object",
          properties: {
            target: { type: "string", description: "Name of the mob to consider" }
          },
          required: ["target"]
        }
      },
      {
        name: "say",
        description: "Speak or emote in the current room.",
        inputSchema: {
          type: "object",
          properties: {
            text: { type: "string", description: "What to say or emote" },
            mode: { type: "string", description: "Mode: say | emote | reply (default: say)" }
          },
          required: ["text"]
        }
      },
      {
        name: "tell",
        description: "Send a private message to a specific player.",
        inputSchema: {
          type: "object",
          properties: {
            target: { type: "string", description: "Player name to message" },
            text:   { type: "string", description: "The message" },
            mode:   { type: "string", description: "Mode: tell | whisper | ask (default: tell)" }
          },
          required: ["target", "text"]
        }
      },
      {
        name: "channel_say",
        description: "Broadcast a message over a global channel.",
        inputSchema: {
          type: "object",
          properties: {
            channel: { type: "string", description: "Channel: shout | gossip | auction | grats | holler" },
            text:    { type: "string", description: "The message to broadcast" }
          },
          required: ["channel", "text"]
        }
      },
      {
        name: "get_item",
        description: "Pick up an item from the room or from a container.",
        inputSchema: {
          type: "object",
          properties: {
            item:      { type: "string",  description: "Name of the item to get" },
            container: { type: "string",  description: "Container to get it from (optional)" },
            count:     { type: "integer", description: "Number of items to get (optional)" }
          },
          required: ["item"]
        }
      },
      {
        name: "drop_item",
        description: "Drop, donate, or junk an item.",
        inputSchema: {
          type: "object",
          properties: {
            item:  { type: "string",  description: "Name of the item" },
            mode:  { type: "string",  description: "Mode: drop | donate | junk (default: drop)" },
            count: { type: "integer", description: "Number of items (optional)" }
          },
          required: ["item"]
        }
      },
      {
        name: "put_item",
        description: "Put an item into a container.",
        inputSchema: {
          type: "object",
          properties: {
            item:      { type: "string",  description: "Name of the item to put" },
            container: { type: "string",  description: "Name of the container" },
            count:     { type: "integer", description: "Number of items (optional)" }
          },
          required: ["item", "container"]
        }
      },
      {
        name: "equip_item",
        description: "Wear, wield, hold, grab, or remove an item.",
        inputSchema: {
          type: "object",
          properties: {
            item:     { type: "string", description: "Name of the item" },
            action:   { type: "string", description: "Action: wear | wield | hold | grab | remove" },
            body_loc: { type: "string", description: "Body location (optional, e.g. head, finger)" }
          },
          required: ["item", "action"]
        }
      },
      {
        name: "consume_item",
        description: "Eat, drink, taste, or sip a consumable item.",
        inputSchema: {
          type: "object",
          properties: {
            item: { type: "string", description: "Name of the item to consume" },
            mode: { type: "string", description: "Mode: eat | drink | taste | sip (default: eat)" }
          },
          required: ["item"]
        }
      },
      {
        name: "cast_spell",
        description: "Cast a spell, optionally at a target.",
        inputSchema: {
          type: "object",
          properties: {
            spell:  { type: "string", description: "Full spell name (e.g. 'cure light wounds')" },
            target: { type: "string", description: "Target mob, player, or object (optional)" }
          },
          required: ["spell"]
        }
      },
      {
        name: "use_magic_item",
        description: "Activate a magic item: quaff a potion, recite a scroll, or use a wand/staff.",
        inputSchema: {
          type: "object",
          properties: {
            item:        { type: "string", description: "Name of the item to activate" },
            mode:        { type: "string", description: "Mode: quaff | recite | use" },
            target_args: { type: "string", description: "Optional target arguments" }
          },
          required: ["item", "mode"]
        }
      },
      {
        name: "shop",
        description: "Interact with a shop NPC: list stock, buy, sell, or get the value of an item.",
        inputSchema: {
          type: "object",
          properties: {
            action: { type: "string", description: "Action: list | buy | sell | value | offer" },
            args:   { type: "string", description: "Item name or number (optional)" }
          },
          required: ["action"]
        }
      },
      {
        name: "practice",
        description: "List your known skills at a guildmaster, or practice a specific skill.",
        inputSchema: {
          type: "object",
          properties: {
            skill: { type: "string", description: "Skill name to practice (omit to list all)" }
          },
          required: []
        }
      },
      {
        name: "save_character",
        description: "Save your character to disk so progress is not lost on disconnect.",
        inputSchema: {
          type: "object",
          properties: {},
          required: []
        }
      },
      {
        name: "send_raw",
        description: "Send an arbitrary command string to the MUD and return the response. " \
                     "Use this as an escape hatch when no structured tool fits.",
        inputSchema: {
          type: "object",
          properties: {
            command: { type: "string", description: "The raw command to send (e.g. 'who', 'help backstab')" }
          },
          required: ["command"]
        }
      }
    ].freeze

    def handle_tools_list(id, _params)
      send_result(id, { tools: TOOL_DEFINITIONS })
    end

    # ── tools/call ──────────────────────────────────────────────

    def handle_tools_call(id, params)
      name = params["name"]
      args = params["arguments"] || {}

      result = invoke_tool(name, args)
      send_result(id, result)
    rescue Error => e
      send_result(id, { content: [{ type: "text", text: "error: #{e.message}" }], isError: true })
    rescue ArgumentError => e
      send_result(id, { content: [{ type: "text", text: "error: #{e.message}" }], isError: true })
    end

    def invoke_tool(name, args)
      case name
      when "mud_connect"    then tool_mud_connect
      when "mud_disconnect" then tool_mud_disconnect
      when "mud_status"     then tool_mud_status
      when "look"           then tool_call(:look, args, %w[target preposition])
      when "examine"        then tool_call(:examine, args, %w[target])
      when "check"          then tool_call_raw(args["kind"])
      when "move"           then tool_call_raw(args["direction"])
      when "flee"           then tool_call_raw("flee")
      when "set_position"   then tool_call_raw(args["position"])
      when "track"          then tool_call_raw("track #{args["target"]}")
      when "attack"         then tool_call_raw("#{args["style"] || "kill"} #{args["target"]}")
      when "skill_strike"   then tool_call_raw("#{args["skill"]} #{args["target"]}")
      when "consider"       then tool_call_raw("consider #{args["target"]}")
      when "say"            then tool_call_raw("#{args["mode"] || "say"} #{args["text"]}")
      when "tell"           then tool_call_raw("#{args["mode"] || "tell"} #{args["target"]} #{args["text"]}")
      when "channel_say"    then tool_call_raw("#{args["channel"]} #{args["text"]}")
      when "get_item"       then tool_get_item(args)
      when "drop_item"      then tool_drop_item(args)
      when "put_item"       then tool_put_item(args)
      when "equip_item"     then tool_equip_item(args)
      when "consume_item"   then tool_call_raw("#{args["mode"] || "eat"} #{args["item"]}")
      when "cast_spell"     then tool_cast_spell(args)
      when "use_magic_item" then tool_use_magic_item(args)
      when "shop"           then tool_shop(args)
      when "practice"       then tool_practice(args)
      when "save_character" then tool_call_raw("save")
      when "send_raw"       then tool_call_raw(args["command"])
      else
        { content: [{ type: "text", text: "Unknown tool: #{name}" }], isError: true }
      end
    end

    # ── Tool implementations ────────────────────────────────────

    def tool_mud_connect
      if @session&.open?
        return text_result("already connected to #{@session.host}:#{@session.port}")
      end
      @session = MudManager::Session.new(host: @host, port: @port)
      @session.open
      welcome = @session.login(@username, @password)
      text_result("connected to #{@host}:#{@port}\n#{welcome}")
    rescue MudManager::Session::Error => e
      error_result(e.message)
    end

    def tool_mud_disconnect
      if @session&.open?
        @session.close
        text_result("disconnected")
      else
        text_result("already disconnected")
      end
    end

    def tool_mud_status
      if @session&.open?
        text_result("connected to #{@session.host}:#{@session.port}")
      else
        text_result("disconnected")
      end
    end

    def tool_call(primitive, args, keys)
      guard_connected!
      kwargs = {}
      keys.each { |k| kwargs[k.to_sym] = args[k] if args.key?(k) }
      send_cmd(@p.send(primitive, **kwargs))
    end

    def tool_call_raw(command)
      guard_connected!
      send_cmd(command)
    end

    def tool_get_item(args)
      guard_connected!
      parts = ["get"]
      parts << args["count"].to_s if args["count"]
      parts << args["item"]
      parts << args["container"] if args["container"]
      send_cmd(parts.join(" "))
    end

    def tool_drop_item(args)
      guard_connected!
      parts = [args["mode"] || "drop"]
      parts << args["count"].to_s if args["count"]
      parts << args["item"]
      send_cmd(parts.join(" "))
    end

    def tool_put_item(args)
      guard_connected!
      parts = ["put"]
      parts << args["count"].to_s if args["count"]
      parts << args["item"]
      parts << args["container"]
      send_cmd(parts.join(" "))
    end

    def tool_equip_item(args)
      guard_connected!
      parts = [args["action"], args["item"]]
      parts << args["body_loc"] if args["body_loc"]
      send_cmd(parts.join(" "))
    end

    def tool_cast_spell(args)
      guard_connected!
      parts = ["cast '#{args["spell"]}'"]
      parts << args["target"] if args["target"]
      send_cmd(parts.join(" "))
    end

    def tool_use_magic_item(args)
      guard_connected!
      parts = [args["mode"], args["item"]]
      parts << args["target_args"] if args["target_args"]
      send_cmd(parts.join(" "))
    end

    def tool_shop(args)
      guard_connected!
      parts = [args["action"]]
      parts << args["args"] if args["args"]
      send_cmd(parts.join(" "))
    end

    def tool_practice(args)
      guard_connected!
      if args["skill"]
        send_cmd("practice #{args["skill"]}")
      else
        send_cmd("practice")
      end
    end

    # ── Helpers ─────────────────────────────────────────────────

    def send_cmd(command)
      @session.drain
      @session.send_command(command)
      text_result(@session.read_until_prompt)
    end

    def guard_connected!
      unless @session&.open?
        raise Error, "not connected — call mud_connect first"
      end
    end

    def text_result(text)
      { content: [{ type: "text", text: text }] }
    end

    def error_result(text)
      { content: [{ type: "text", text: text }], isError: true }
    end

    def auto_connect
      return unless @username && @password
      begin
        @session = MudManager::Session.new(host: @host, port: @port)
        @session.open
        @session.login(@username, @password)
        send_event("auto-connected to #{@host}:#{@port}")
      rescue MudManager::Session::Error => e
        @session = nil
        send_event("auto-connect failed: #{e.message}")
      end
    end

    # ── JSON-RPC wire ───────────────────────────────────────────

    def send_result(id, result)
      write({
        jsonrpc: "2.0",
        id: id,
        result: result
      })
    end

    def send_error(id, code, message, data: nil)
      err = { code: code, message: message }
      err[:data] = data if data
      write({
        jsonrpc: "2.0",
        id: id,
        error: err
      })
    end

    def send_event(text)
      write({
        jsonrpc: "2.0",
        method: "notifications/message",
        params: {
          level: "info",
          message: "[mud_mcp] #{text}"
        }
      })
    end

    def write(msg)
      $stdout.puts(JSON.generate(msg))
      $stdout.flush
    end
  end

  class Error < StandardError; end
end

if __FILE__ == $PROGRAM_NAME
  MudMcp::Server.new.start
end
