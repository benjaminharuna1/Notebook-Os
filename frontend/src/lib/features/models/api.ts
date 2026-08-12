import { api } from '$lib/core/api/client';
import type { ModelConfig } from './types';

export async function listModels(): Promise<{ available: ModelConfig[]; active: ModelConfig }> {
  return api.get<{ available: ModelConfig[]; active: ModelConfig }>('/models');
}

export async function switchModel(modelId: string): Promise<{ success: boolean }> {
  return api.post<{ success: boolean }>('/models/switch', { model_id: modelId });
}

export async function listOllamaModels(): Promise<{ models: string[] }> {
  return api.get<{ models: string[] }>('/models/ollama/available');
}
