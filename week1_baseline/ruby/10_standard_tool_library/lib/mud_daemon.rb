require "json"
require "socket"
require "fileutils"
require "mud_manager"

module MudDaemon
  PORT_DIR  = ENV["MUD_MANAGER_DIR"] || File.expand_path("~/.mud_manager")
  PORT_FILE = File.join(PORT_DIR, "port")

  class Server
    def initialize
      @sessions = {}
      @running  = false
    end

    def start
      FileUtils.mkdir_p(PORT_DIR)

      @server = TCPServer.new("127.0.0.1", 0)
      @mutex  = Mutex.new
      port    = @server.addr[1]
      File.write(PORT_FILE, port)
      warn "[mud_daemon] listening on 127.0.0.1:#{port} (pid #{Process.pid})"

      @running = true
      trap("INT")  { shutdown }
      trap("TERM") { shutdown }

      loop do
        client = @server.accept
        Thread.new(client) { |c| handle_client(c) }
      end
    end

    def shutdown
      @running = false
      @sessions.each_value(&:close)
      @server&.close
      File.delete(PORT_FILE) if File.exist?(PORT_FILE)
    end

    private

    def handle_client(client)
      request = JSON.parse(client.gets)
      response = dispatch(request)
      client.write(JSON.generate(response) + "\n")
    rescue JSON::ParserError
      client.write(JSON.generate({ ok: false, error: "invalid JSON" }) + "\n")
    ensure
      client.close
    end

    def dispatch(request)
      cmd = request["cmd"]

      case cmd
      when "ping"
        { ok: true, data: "pong" }

      when "connect"
        handle_connect(request)

      when "send"
        handle_send(request)

      when "disconnect"
        handle_disconnect(request)

      when "status"
        handle_status(request)

      else
        { ok: false, error: "unknown command: #{cmd.inspect}" }
      end
    rescue MudManager::Session::Error => e
      { ok: false, error: e.message }
    rescue ArgumentError => e
      { ok: false, error: e.message }
    end

    def handle_connect(request)
      sid  = request["session"] || "default"
      host = request["host"] || MudManager::Session::DEFAULT_HOST
      port = request["port"] || MudManager::Session::DEFAULT_PORT
      name = request["name"]
      pwd  = request["password"]

      unless name && pwd
        return { ok: false, error: "name and password are required" }
      end

      session = MudManager::Session.new(host: host, port: port)
      session.open
      welcome = session.login(name, pwd) rescue "login completed"
      @mutex.synchronize do
        # Force-close any stale session for the same key before storing the new one
        if (old = @sessions[sid])
          old.close rescue nil
        end
        @sessions[sid] = session
      end
      { ok: true, data: "connected to #{host}:#{port}\n#{welcome}" }
    end

    def handle_send(request)
      sid     = request["session"] || "default"
      command = request["command"]

      unless command && !command.empty?
        return { ok: false, error: "command is required" }
      end

      @mutex.synchronize do
        session = @sessions[sid]
        unless session&.open?
          return { ok: false, error: "not connected — call connect first" }
        end

        session.drain
        session.send_command(command)
        response = session.read_until_prompt
        { ok: true, data: response }
      end
    end

    def handle_disconnect(request)
      sid = request["session"] || "default"
      @mutex.synchronize do
        session = @sessions[sid]
        if session&.open?
          session.send_command("quit") rescue nil
          session.read_until_prompt(timeout: 2) rescue nil
          session.close
          @sessions.delete(sid)
          { ok: true, data: "disconnected" }
        else
          { ok: true, data: "already disconnected" }
        end
      end
    end

    def handle_status(request)
      sid = request["session"] || "default"
      @mutex.synchronize do
        session = @sessions[sid]
        if session&.open?
          { ok: true, data: { connected: true, host: session.host, port: session.port } }
        else
          { ok: true, data: { connected: false } }
        end
      end
    end
  end
end

if __FILE__ == $PROGRAM_NAME
  MudDaemon::Server.new.start
end
