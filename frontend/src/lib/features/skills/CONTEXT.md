# Skills Feature Contract

AI skill catalog, installation, and management.

## What it does

Browses available AI skills from a catalog, installs/uninstalls skills, toggles them on/off. Skills are JSON manifests that provide specialized instructions and workflows for specific research tasks.

## API endpoints called

| Endpoint | Method | Purpose |
|---|---|---|
| `/skills` | GET | List installed skills |
| `/skills/catalog` | GET | Browse available skills |
| `/skills/install` | POST | Install a skill |
| `/skills/{id}/enable` | POST | Enable/disable a skill |
| `/skills/{id}` | DELETE | Uninstall a skill |
| `/skills/import` | POST | Import custom skill manifest |

## State managed

No global store — skill data fetched on route load.

## Components

No feature-specific components — skills UI is in `routes/skills/`.

## Types

- `SkillManifest`: id, name, version, description, category, author, instructions, example_workflow, tags
- `InstalledSkill`: skill (manifest), enabled, installed_at
- `CatalogSkill`: skill (manifest), installed
