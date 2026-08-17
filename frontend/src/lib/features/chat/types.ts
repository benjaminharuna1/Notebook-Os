export interface ChatSession {
  id: string;
  title?: string;
  model_used?: string;
  created_at?: string;
  updated_at?: string;
}

export interface SourceChunk {
  chunk_id: string;
  title: string;
  page?: number;
  document_id?: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  sources?: SourceChunk[];
  model_used?: string;
  created_at?: string;
}
