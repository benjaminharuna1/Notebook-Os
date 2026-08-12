class AIRouter:
    def __init__(self):
        self._routing_rules = {}

    def should_use_cloud(self, query: str, context_size: int) -> bool:
        return False

    def get_provider_for_model(self, model_config: dict):
        return model_config["provider"]
