export interface SkillManifest {
  id: string;
  name: string;
  version: string;
  description: string;
  category: string;
  author: string;
  instructions: string;
  example_workflow?: string;
  tags: string[];
}

export interface InstalledSkill {
  skill: SkillManifest;
  enabled: boolean;
  installed_at?: string;
}

export interface CatalogSkill {
  skill: SkillManifest;
  installed: boolean;
}
