export interface ChatSession {
  id: string;
  title?: string;
  model_used?: string;
  created_at?: string;
  updated_at?: string;
}

export interface ChatMessage {
  id: string;
  session_id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  sources?: string;
  model_used?: string;
  created_at?: string;
}
