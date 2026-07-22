require_relative "openai"

module Boukensha
  module Backends
    class OpenCode < OpenAI
      BASE_URL = "https://opencode.ai/zen/v1/chat/completions"

      def url
        BASE_URL
      end

      MODELS = {
        "deepseek-v4-flash-free" => {
          context_window: 128_000,
          cost_per_million: { input: 0, output: 0 },
          usage_unit: :tokens
        },
        "gpt-5-nano" => {
          context_window: 128_000,
          cost_per_million: { input: 0, output: 0 },
          usage_unit: :tokens
        },
        "big-pickle" => {
          context_window: 128_000,
          cost_per_million: { input: 0, output: 0 },
          usage_unit: :tokens
        },
        "mimo-v2.5-free" => {
          context_window: 128_000,
          cost_per_million: { input: 0, output: 0 },
          usage_unit: :tokens
        },
        "north-mini-code-free" => {
          context_window: 128_000,
          cost_per_million: { input: 0, output: 0 },
          usage_unit: :tokens
        },
        "nemotron-3-ultra-free" => {
          context_window: 128_000,
          cost_per_million: { input: 0, output: 0 },
          usage_unit: :tokens
        }
      }.freeze
    end
  end
end
