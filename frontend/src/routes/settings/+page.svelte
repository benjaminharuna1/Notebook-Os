<script lang="ts">
  import { onMount } from 'svelte';
  import { getSettings, updateSettings } from '$lib/features/settings/api';
  import type { UserSettings } from '$lib/features/settings/types';
  import Header from '$lib/core/components/layout/Header.svelte';
  import { toasts } from '$lib/core/stores/toasts';

  let settings = $state<UserSettings>({} as UserSettings);
  let loading = $state(true);
  let saving = $state(false);

  onMount(async () => {
    const res = await getSettings();
    settings = res.settings;
    loading = false;
  });

  async function save() {
    saving = true;
    try {
      const res = await updateSettings(settings);
      settings = res.settings;
      toasts.add('Settings saved', 'success');
    } catch (e) {
      toasts.add((e as Error).message, 'error');
    } finally {
      saving = false;
    }
  }
</script>

<div class="flex h-full flex-col">
  <Header />
  <div class="flex-1 overflow-auto p-6">
    <h1 class="mb-6 text-2xl font-bold text-slate-900">Settings</h1>

    {#if loading}
      <p class="text-slate-400">Loading...</p>
    {:else}
      <form onsubmit={(e) => { e.preventDefault(); save(); }} class="max-w-2xl space-y-8">
        <section>
          <h2 class="mb-4 text-lg font-semibold text-slate-800">Chunking</h2>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="mb-1 block text-sm font-medium text-slate-700">Chunk Size</label>
              <input type="number" bind:value={settings.chunk_size} class="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm" />
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium text-slate-700">Chunk Overlap</label>
              <input type="number" bind:value={settings.chunk_overlap} class="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm" />
            </div>
          </div>
        </section>

        <section>
          <h2 class="mb-4 text-lg font-semibold text-slate-800">Default Models</h2>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="mb-1 block text-sm font-medium text-slate-700">Provider</label>
              <select bind:value={settings.provider} class="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm">
                <option value="ollama">Ollama</option>
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="google">Google</option>
              </select>
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium text-slate-700">Default LLM</label>
              <input type="text" bind:value={settings.default_llm} class="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm" />
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium text-slate-700">Embedding Model</label>
              <input type="text" bind:value={settings.default_embedding_model} class="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm" />
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium text-slate-700">Ollama Model</label>
              <input type="text" bind:value={settings.ollama_model} class="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm" />
            </div>
          </div>
        </section>

        <section>
          <h2 class="mb-4 text-lg font-semibold text-slate-800">API Keys</h2>
          <div class="space-y-4">
            <div>
              <label class="mb-1 block text-sm font-medium text-slate-700">OpenAI API Key</label>
              <input type="password" bind:value={settings.openai_api_key} class="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm" placeholder="sk-..." />
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium text-slate-700">Anthropic API Key</label>
              <input type="password" bind:value={settings.anthropic_api_key} class="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm" placeholder="sk-ant-..." />
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium text-slate-700">Google API Key</label>
              <input type="password" bind:value={settings.google_api_key} class="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm" placeholder="AIza..." />
            </div>
          </div>
        </section>

        <section>
          <h2 class="mb-4 text-lg font-semibold text-slate-800">Generation</h2>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="mb-1 block text-sm font-medium text-slate-700">Max Tokens</label>
              <input type="number" bind:value={settings.max_tokens} class="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm" />
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium text-slate-700">Temperature</label>
              <input type="number" step="0.1" min="0" max="2" bind:value={settings.temperature} class="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm" />
            </div>
          </div>
        </section>

        <div class="flex gap-3">
          <button type="submit" disabled={saving} class="rounded-lg bg-indigo-600 px-6 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50">
            {saving ? 'Saving...' : 'Save Settings'}
          </button>
        </div>
      </form>
    {/if}
  </div>
</div>
