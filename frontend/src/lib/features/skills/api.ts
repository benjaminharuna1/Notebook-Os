import { api } from '$lib/core/api/client';
import type { CatalogSkill, InstalledSkill, SkillManifest } from './types';

export async function listInstalledSkills(): Promise<{ skills: InstalledSkill[] }> {
  return api.get<{ skills: InstalledSkill[] }>('/skills');
}

export async function listCatalog(): Promise<{ catalog: CatalogSkill[] }> {
  return api.get<{ catalog: CatalogSkill[] }>('/skills/catalog');
}

export async function installSkill(skillId: string): Promise<{ success: boolean }> {
  return api.post<{ success: boolean }>('/skills/install', { skill_id: skillId });
}

export async function setSkillEnabled(skillId: string, enabled: boolean): Promise<{ success: boolean }> {
  return api.post<{ success: boolean }>(`/skills/${skillId}/enable`, { enabled });
}

export async function uninstallSkill(skillId: string): Promise<{ success: boolean }> {
  return api.delete<{ success: boolean }>(`/skills/${skillId}`);
}

export async function importSkill(manifest: SkillManifest): Promise<{ success: boolean }> {
  return api.post<{ success: boolean }>('/skills/import', manifest);
}
