<script lang="ts">
  import { onMount } from 'svelte';
  import { getSettings, updateSettings, getLocalStatus, getCatalog } from '$lib/features/settings/api';
  import type { LocalStatus, ModelCatalog, UserSettings } from '$lib/features/settings/types';
  import Header from '$lib/core/components/layout/Header.svelte';
  import PasswordInput from '$lib/core/components/ui/PasswordInput.svelte';
  import { toasts } from '$lib/core/stores/toasts';

  let settings = $state<UserSettings>({} as UserSettings);
  let localStatus = $state<LocalStatus | null>(null);
  let catalog = $state<ModelCatalog | null>(null);
  let loading = $state(true);
  let saving = $state(false);

  onMount(async () => {
    const res = await getSettings();
    settings = res.settings;
    localStatus = await getLocalStatus().catch(() => null);
    catalog = await getCatalog().catch(() => null);
    loading = false;
  });

  function applyTier(tier: 'low' | 'medium' | 'high') {
    settings.device_tier = tier;
    const rec = catalog?.embeddings?.[0];
    const llm = catalog?.llm?.[0];
    if (llm) {
      settings.default_llm = llm;
      settings.ollama_model = llm;
    }
    if (rec) {
      settings.embedding_provider = rec.provider as 'fastembed' | 'ollama';
      settings.embedding_model = rec.model;
    }
  }

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
    <div class="mb-6 flex items-center justify-between">
      <h1 class="text-2xl font-bold text-slate-900">Settings</h1>
      {#if localStatus && !localStatus.ollama_running}
        <span class="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium text-amber-700">
          Ollama not running — using local fastembed embeddings
        </span>
      {/if}
    </div>

    {#if loading}
      <p class="text-slate-400">Loading...</p>
    {:else}
      <form onsubmit={(e) => { e.preventDefault(); save(); }} class="max-w-2xl space-y-8">
        <section>
          <h2 class="mb-4 text-lg font-semibold text-slate-800">Device &amp; Local Models</h2>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="mb-1 block text-sm font-medium text-slate-700">Device Tier</label>
              <select bind:value={settings.device_tier} onchange={(e) => applyTier(e.currentTarget.value as 'low' | 'medium' | 'high')} class="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm">
                <option value="low">Low-end</option>
                <option value="medium">Medium</option>
                <option value="high">High-end</option>
              </select>
              <p class="mt-1 text-xs text-slate-400">
                {#if localStatus}Recommended local model for this tier: {localStatus.recommended_local_model}{/if}
              </p>
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium text-slate-700">Default Local LLM</label>
              <input type="text" bind:value={settings.default_llm} class="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm" />
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium text-slate-700">Embedding Provider</label>
              <select bind:value={settings.embedding_provider} class="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm">
                <option value="fastembed">fastembed (ONNX — no Ollama needed)</option>
                <option value="ollama">Ollama (nomic-embed-text)</option>
              </select>
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium text-slate-700">Embedding Model</label>
              <input type="text" bind:value={settings.embedding_model} class="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm" />
            </div>
          </div>
          {#if localStatus && localStatus.ollama_models.length > 0}
            <p class="mt-2 text-xs text-slate-400">Installed Ollama models: {localStatus.ollama_models.join(', ')}</p>
          {/if}
        </section>

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

        <section class="rounded-lg border border-slate-200 p-4">
          <div class="mb-2 flex items-center justify-between">
            <h2 class="text-lg font-semibold text-slate-800">Cloud Models (Optional)</h2>
            <label class="flex items-center gap-2 text-sm text-slate-600">
              <input type="checkbox" bind:checked={settings.cloud_enabled} class="h-4 w-4 rounded border-slate-300" />
              Enable cloud models
            </label>
          </div>
          <p class="mb-4 text-xs text-slate-400">
            The app runs fully local by default. Enable only if you want to use API models (good for low-end devices) or
            higher-quality responses.
          </p>

          {#if settings.cloud_enabled}
            <div class="grid grid-cols-2 gap-4">
              <div>
                <label class="mb-1 block text-sm font-medium text-slate-700">OpenAI Model</label>
                <input type="text" bind:value={settings.openai_model} class="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm" placeholder="gpt-4o-mini" />
              </div>
              <div>
                <label class="mb-1 block text-sm font-medium text-slate-700">OpenAI API Key</label>
                <PasswordInput bind:value={settings.openai_api_key} placeholder="sk-..." />
              </div>
              <div>
                <label class="mb-1 block text-sm font-medium text-slate-700">Anthropic Model</label>
                <input type="text" bind:value={settings.anthropic_model} class="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm" placeholder="claude-3-5-haiku-latest" />
              </div>
              <div>
                <label class="mb-1 block text-sm font-medium text-slate-700">Anthropic API Key</label>
                <PasswordInput bind:value={settings.anthropic_api_key} placeholder="sk-ant-..." />
              </div>
              <div>
                <label class="mb-1 block text-sm font-medium text-slate-700">Google Model</label>
                <input type="text" bind:value={settings.google_model} class="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm" placeholder="gemini-2.0-flash" />
              </div>
              <div>
                <label class="mb-1 block text-sm font-medium text-slate-700">Google API Key</label>
                <PasswordInput bind:value={settings.google_api_key} placeholder="AIza..." />
              </div>
            </div>
          {:else}
            <p class="text-sm text-slate-400">Cloud models disabled — everything runs on your device.</p>
          {/if}
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
