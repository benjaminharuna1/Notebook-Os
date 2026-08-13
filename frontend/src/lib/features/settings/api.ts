import { api } from '$lib/core/api/client';
import type { LocalStatus, ModelCatalog, UserSettings } from './types';

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
