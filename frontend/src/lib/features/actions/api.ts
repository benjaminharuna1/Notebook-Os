import { api } from '$lib/core/api/client';
import type { ActionInfo } from './types';

export async function listActions(): Promise<ActionInfo[]> {
  const res = await api.get<{ actions: ActionInfo[] }>('/actions');
  return res.actions ?? [];
}

export async function pauseActionRequest(id: string): Promise<ActionInfo> {
  return api.post<ActionInfo>(`/actions/${id}/pause`, {});
}

export async function resumeActionRequest(id: string): Promise<ActionInfo> {
  return api.post<ActionInfo>(`/actions/${id}/resume`, {});
}
