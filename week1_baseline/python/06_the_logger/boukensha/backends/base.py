from boukensha.errors import UnsupportedModelError


class Base:
    MODELS = {}

    def __init__(self, model):
        self.model = self._validate_model(model)
        self._model_info = self._model_info_for(model)

    @classmethod
    def _model_info_for(cls, model):
        return cls.MODELS.get(str(model))

    @classmethod
    def _validate_model(cls, model):
        model = str(model)
        if cls._model_info_for(model):
            return model
        supported = ", ".join(sorted(cls.MODELS.keys()))
        raise UnsupportedModelError(f"{cls.__name__} does not support model '{model}'. Supported models: {supported}")

    @property
    def context_window(self):
        return self._model_info["context_window"]

    @property
    def input_token_cost_per_million(self):
        return self._model_info["cost_per_million"]["input"]

    @property
    def output_token_cost_per_million(self):
        return self._model_info["cost_per_million"]["output"]

    @property
    def usage_unit(self):
        return self._model_info["usage_unit"]

    @property
    def usage_level(self):
        return self._model_info.get("usage_level")

    def estimate_cost(self, input_tokens, output_tokens):
        inp = self.input_token_cost_per_million
        out = self.output_token_cost_per_million
        if inp is None or out is None:
            return None
        return (input_tokens * inp + output_tokens * out) / 1_000_000.0
