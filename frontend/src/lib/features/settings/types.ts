export interface UserSettings {
  chunk_size: number;
  chunk_overlap: number;
  default_llm: string;
  default_embedding_model: string;
  provider: string;
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
