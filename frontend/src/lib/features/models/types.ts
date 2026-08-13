export interface ModelConfig {
  id: string;
  name: string;
  provider: string;
  model_id: string;
  is_active: boolean;
  is_default: boolean;
  config?: string;
  source?: 'local' | 'cloud';
}
