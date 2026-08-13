import { api } from '$lib/core/api/client';
import type { Project } from './types';

export async function listProjects(): Promise<{ projects: Project[] }> {
  return api.get<{ projects: Project[] }>('/projects');
}

export async function createProject(name: string, description = ''): Promise<Project> {
  return api.post<Project>('/projects', { name, description });
}

export async function getProject(id: string): Promise<Project> {
  return api.get<Project>(`/projects/${id}`);
}

export async function updateProject(id: string, data: { name?: string; description?: string }): Promise<Project> {
  return api.patch<Project>(`/projects/${id}`, data);
}

export async function deleteProject(id: string): Promise<{ success: boolean }> {
  return api.delete<{ success: boolean }>(`/projects/${id}`);
}
