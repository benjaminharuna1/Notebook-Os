export interface UserSettings {
  chunk_size: number;
  chunk_overlap: number;
  default_llm: string;
  default_embedding_model: string;
  embedding_backend: string;
  provider: string;
  local_model: string;
  device_tier: 'low' | 'medium' | 'high';
  embedding_provider: 'fastembed' | 'ollama';
  embedding_model: string;
  cloud_enabled: boolean;
  openai_api_key: string;
  anthropic_api_key: string;
  google_api_key: string;
  openai_model: string;
  anthropic_model: string;
  google_model: string;
  ollama_model: string;
  max_tokens: number;
  temperature: number;
}

export interface LocalStatus {
  ollama_running: boolean;
  ollama_models: string[];
  device_tier: string;
  recommended_local_model: string;
  recommended_embedding: { provider: string; model: string };
}

export interface ModelCatalog {
  device_tier: string;
  llm: string[];
  embeddings: { provider: string; model: string; dim: number; requires: string; note: string }[];
  cloud_presets: Record<string, string[]>;
}
