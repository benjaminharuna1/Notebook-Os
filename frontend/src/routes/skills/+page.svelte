<script lang="ts">
  import Header from '$lib/core/components/layout/Header.svelte';
  import { onMount } from 'svelte';
  import { toasts } from '$lib/core/stores/toasts';
  import {
    listInstalledSkills,
    listCatalog,
    installSkill,
    setSkillEnabled,
    uninstallSkill,
    importSkill,
  } from '$lib/features/skills/api';
  import type { CatalogSkill, InstalledSkill, SkillManifest } from '$lib/features/skills/types';

  let installed = $state<InstalledSkill[]>([]);
  let catalog = $state<CatalogSkill[]>([]);
  let loading = $state(true);

  let importOpen = $state(false);
  let importText = $state('');
  let importError = $state('');

  const IMPORT_PLACEHOLDER = '{&quot;id&quot;: &quot;my-skill&quot;, &quot;name&quot;: &quot;My Skill&quot;, &quot;description&quot;: &quot;...&quot;, &quot;instructions&quot;: &quot;...&quot;}';

  const categoryColors: Record<string, string> = {
    research: 'bg-indigo-100 text-indigo-700',
    citation: 'bg-emerald-100 text-emerald-700',
    ideation: 'bg-amber-100 text-amber-700',
    general: 'bg-slate-100 text-slate-700',
  };

  async function load() {
    loading = true;
    try {
      const [inst, cat] = await Promise.all([listInstalledSkills(), listCatalog()]);
      installed = inst.skills;
      catalog = cat.catalog;
    } catch (err) {
      toasts.add((err as Error).message, 'error');
    } finally {
      loading = false;
    }
  }

  onMount(load);

  async function handleInstall(skill: CatalogSkill) {
    try {
      await installSkill(skill.skill.id);
      toasts.add(`Installed "${skill.skill.name}"`, 'success');
      await load();
    } catch (err) {
      toasts.add((err as Error).message, 'error');
    }
  }

  async function handleToggle(item: InstalledSkill, enabled: boolean) {
    try {
      await setSkillEnabled(item.skill.id, enabled);
      item.enabled = enabled;
    } catch (err) {
      toasts.add((err as Error).message, 'error');
    }
  }

  async function handleUninstall(item: InstalledSkill) {
    if (!confirm(`Uninstall "${item.skill.name}"?`)) return;
    try {
      await uninstallSkill(item.skill.id);
      installed = installed.filter((i) => i.skill.id !== item.skill.id);
      catalog = catalog.map((c) =>
        c.skill.id === item.skill.id ? { ...c, installed: false } : c,
      );
      toasts.add(`Uninstalled "${item.skill.name}"`, 'success');
    } catch (err) {
      toasts.add((err as Error).message, 'error');
    }
  }

  async function handleImport() {
    importError = '';
    let manifest: SkillManifest;
    try {
      manifest = JSON.parse(importText);
    } catch {
      importError = 'Invalid JSON';
      return;
    }
    try {
      await importSkill(manifest);
      importText = '';
      importOpen = false;
      toasts.add(`Imported "${manifest.name || manifest.id}"`, 'success');
      await load();
    } catch (err) {
      importError = (err as Error).message;
    }
  }
</script>

<div class="flex h-full flex-col">
  <Header />
  <div class="flex-1 overflow-auto p-6">
    <div class="mb-6 flex items-center justify-between">
      <h1 class="text-2xl font-bold text-slate-900">Skills</h1>
      <button
        onclick={() => (importOpen = !importOpen)}
        class="rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700"
      >
        {importOpen ? 'Close Import' : '+ Import Skill'}
      </button>
    </div>

    {#if importOpen}
      <div class="mb-6 rounded-lg border border-slate-200 p-4">
        <p class="mb-2 text-sm text-slate-600">
          Paste a skill manifest (JSON with <code class="rounded bg-slate-100 px-1">id</code>,
          <code class="rounded bg-slate-100 px-1">name</code>,
          <code class="rounded bg-slate-100 px-1">description</code>,
          <code class="rounded bg-slate-100 px-1">instructions</code>).
        </p>
        <textarea
          bind:value={importText}
          rows="8"
          class="w-full rounded-lg border border-slate-300 p-3 font-mono text-xs text-slate-800 focus:border-indigo-500 focus:outline-none"
          placeholder={IMPORT_PLACEHOLDER}
        ></textarea>
        {#if importError}
          <p class="mt-2 text-sm text-red-500">{importError}</p>
        {/if}
        <button
          onclick={handleImport}
          class="mt-3 rounded-lg bg-slate-800 px-3 py-2 text-sm font-medium text-white hover:bg-slate-900"
        >
          Import
        </button>
      </div>
    {/if}

    {#if loading}
      <div class="text-center text-slate-400">Loading...</div>
    {:else}
      <section class="mb-8">
        <h2 class="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Installed ({installed.length})
        </h2>
        {#if installed.length === 0}
          <p class="rounded-lg border border-dashed border-slate-300 p-4 text-sm text-slate-400">
            No skills installed. Browse the catalog below to enable your first skill.
          </p>
        {:else}
          <div class="space-y-3">
            {#each installed as item (item.skill.id)}
              <div class="flex items-center gap-4 rounded-lg border border-slate-200 p-4">
                <div class="min-w-0 flex-1">
                  <div class="flex items-center gap-2">
                    <span class="font-medium text-slate-900">{item.skill.name}</span>
                    <span
                      class="rounded px-1.5 py-0.5 text-xs {categoryColors[item.skill.category] || categoryColors['general']}"
                    >
                      {item.skill.category}
                    </span>
                    <span class="text-xs text-slate-400">v{item.skill.version}</span>
                  </div>
                  <p class="mt-0.5 text-sm text-slate-500">{item.skill.description}</p>
                </div>
                <label class="flex cursor-pointer items-center gap-2 text-sm text-slate-600">
                  <input
                    type="checkbox"
                    class="peer sr-only"
                    checked={item.enabled}
                    onchange={(e) => handleToggle(item, (e.target as HTMLInputElement).checked)}
                  />
                  <span
                    class="h-5 w-9 rounded-full bg-slate-300 transition-colors peer-checked:bg-indigo-600 after:ml-0.5 after:block after:h-4 after:w-4 after:rounded-full after:bg-white after:transition-transform peer-checked:after:translate-x-4"
                  ></span>
                  {item.enabled ? 'Active' : 'Paused'}
                </label>
                <button
                  onclick={() => handleUninstall(item)}
                  class="text-xs text-red-500 hover:text-red-700"
                >
                  Uninstall
                </button>
              </div>
            {/each}
          </div>
        {/if}
      </section>

      <section>
        <h2 class="mb-3 text-sm font-semibold uppercase tracking-wide text-slate-400">
          Catalog
        </h2>
        <div class="space-y-3">
          {#each catalog as entry (entry.skill.id)}
            <div class="flex items-center gap-4 rounded-lg border border-slate-200 p-4">
              <div class="min-w-0 flex-1">
                <div class="flex items-center gap-2">
                  <span class="font-medium text-slate-900">{entry.skill.name}</span>
                  <span
                    class="rounded px-1.5 py-0.5 text-xs {categoryColors[entry.skill.category] || categoryColors['general']}"
                  >
                    {entry.skill.category}
                  </span>
                  <span class="text-xs text-slate-400">v{entry.skill.version}</span>
                </div>
                <p class="mt-0.5 text-sm text-slate-500">{entry.skill.description}</p>
                {#if entry.skill.tags.length > 0}
                  <div class="mt-1.5 flex flex-wrap gap-1">
                    {#each entry.skill.tags as tag}
                      <span class="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-500">{tag}</span>
                    {/each}
                  </div>
                {/if}
              </div>
              {#if entry.installed}
                <span class="text-xs font-medium text-emerald-600">Installed</span>
              {:else}
                <button
                  onclick={() => handleInstall(entry)}
                  class="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700"
                >
                  Install
                </button>
              {/if}
            </div>
          {/each}
        </div>
      </section>
    {/if}
  </div>
</div>
