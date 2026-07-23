require_relative "base"

module Boukensha
  module Backends
    class OpenCode < Base
      BASE_URL = "https://api.opencode.ai/v1"
      SUPPORTED_MODELS = %w[deepseek-v4-flash-free].freeze

      def initialize(api_key:, model:)
        raise ArgumentError, "api_key is required for OpenCode" unless api_key
        raise UnsupportedModelError, "#{model} is not supported by OpenCode. Supported models: #{SUPPORTED_MODELS.join(", ")}" unless SUPPORTED_MODELS.include?(model)

        @api_key = api_key
        @model   = model
      end

      def api_key
        @api_key
      end

      def base_url
        BASE_URL
      end
    end
  end
end
