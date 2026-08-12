import { api } from '$lib/core/api/client';
import type { UserSettings } from './types';

export async function getSettings(): Promise<{ settings: UserSettings }> {
  return api.get<{ settings: UserSettings }>('/settings');
}

export async function updateSettings(settings: Partial<UserSettings>): Promise<{ settings: UserSettings }> {
  return api.put<{ settings: UserSettings }>('/settings', settings);
}
