import { api } from '$lib/core/api/client';
import type { LocalStatus, ModelCatalog, ModelDownload, UserSettings } from './types';

export async function getSettings(): Promise<{ settings: UserSettings }> {
  return api.get<{ settings: UserSettings }>('/settings');
}

export async function updateSettings(settings: Partial<UserSettings>): Promise<{ settings: UserSettings }> {
  return api.put<{ settings: UserSettings }>('/settings', settings);
}

export async function getLocalStatus(): Promise<LocalStatus> {
  return api.get<LocalStatus>('/local/status');
}

export async function getCatalog(): Promise<ModelCatalog> {
  return api.get<ModelCatalog>('/models/catalog');
}

export async function startModelDownload(key: string): Promise<{ status: string }> {
  return api.post<{ status: string }>('/models/hf/download', { key });
}

export async function getModelDownloads(): Promise<{ downloads: ModelDownload[] }> {
  return api.get<{ downloads: ModelDownload[] }>('/models/hf/downloads');
}

export async function downloadCustomModel(url: string, name?: string): Promise<{ status: string }> {
  return api.post<{ status: string }>('/models/hf/custom-download', { url, name });
}

export async function removeCustomModel(key: string): Promise<{ success: boolean }> {
  return api.delete<{ success: boolean }>(`/models/hf/custom/${key}`);
}
