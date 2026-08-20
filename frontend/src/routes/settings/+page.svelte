<script lang="ts">
  import { onDestroy, onMount } from 'svelte';
  import { getSettings, updateSettings, getLocalStatus, getCatalog, startModelDownload, getModelDownloads, downloadCustomModel, removeCustomModel } from '$lib/features/settings/api';
  import type { LocalStatus, ModelCatalog, ModelDownload, UserSettings } from '$lib/features/settings/types';
  import Header from '$lib/core/components/layout/Header.svelte';
  import PasswordInput from '$lib/core/components/ui/PasswordInput.svelte';
  import { toasts } from '$lib/core/stores/toasts';

  let settings = $state<UserSettings>({} as UserSettings);
  let localStatus = $state<LocalStatus | null>(null);
  let catalog = $state<ModelCatalog | null>(null);
  let downloads = $state<ModelDownload[]>([]);
  let loading = $state(true);
  let saving = $state(false);
  let pollTimer: ReturnType<typeof setInterval> | null = null;

  let llmSelection = $state('');
  let embeddingSelection = $state('');
  let customUrl = $state('');
  let customName = $state('');
  let customDownloading = $state(false);
  let customError = $state('');

  const chatOptions = $derived.by(() => {
    const opts: { id: string; name: string; group: string; provider: string }[] = [];
    for (const m of localStatus?.ollama_models ?? []) {
      opts.push({ id: `ollama:${m}`, name: m, group: 'Ollama models (installed)', provider: 'ollama' });
    }
    for (const d of downloads) {
      if (d.kind === 'chat' && d.downloaded) {
        opts.push({ id: `local:${d.key}`, name: d.name, group: 'Downloaded local models (llama.cpp)', provider: 'local' });
      }
    }
    if (llmSelection && !opts.some((o) => o.id === llmSelection)) {
      const [, ...rest] = llmSelection.split(':');
      opts.push({ id: llmSelection, name: rest.join(':'), group: 'Not installed (saved selection)', provider: '' });
    }
    return opts;
  });

  const chatGroups = $derived.by(() => [...new Set(chatOptions.map((o) => o.group))]);

  const embeddingOptions = $derived.by(() =>
    (catalog?.embeddings ?? []).map((e) => ({ id: `${e.provider}|${e.model}`, provider: e.provider, model: e.model, note: e.note, dim: e.dim }))
  );

  const embeddingDownload = $derived.by(() => {
    if (!embeddingSelection) return null;
    const [provider, model] = embeddingSelection.split('|');
    if (provider !== 'local') return null;
    return downloads.find((d) => d.key === model) ?? null;
  });

  const chatDownloads = $derived.by(() =>
    downloads.filter((d) => d.kind === 'chat' && !d.downloaded && !d.custom)
  );

  const customModels = $derived.by(() =>
    downloads.filter((d) => d.custom)
  );

  const parsedUrl = $derived.by(() => {
    if (!customUrl.trim()) return null;
    return parseHfUrl(customUrl.trim());
  });

  const hasActiveDownload = $derived.by(() =>
    downloads.some((d) => d.status === 'downloading')
  );

  function syncDownloads(list: ModelDownload[]) {
    downloads = list;
    if (list.some((d) => d.status === 'downloading')) startPolling();
  }

  async function refreshDownloads() {
    try {
      const res = await getModelDownloads();
      downloads = res.downloads;
      if (!downloads.some((d) => d.status === 'downloading')) stopPolling();
    } catch {
      stopPolling();
    }
  }

  function startPolling() {
    if (pollTimer) return;
    pollTimer = setInterval(refreshDownloads, 1200);
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }

  onDestroy(stopPolling);

  async function download(key: string) {
    try {
      await startModelDownload(key);
      downloads = downloads.map((d) => (d.key === key ? { ...d, status: 'downloading', progress: 0 } : d));
      startPolling();
      await refreshDownloads();
    } catch (e) {
      toasts.add((e as Error).message, 'error');
    }
  }

  async function downloadCustom() {
    if (!customUrl.trim()) return;
    customDownloading = true;
    customError = '';
    try {
      await downloadCustomModel(customUrl.trim(), customName.trim() || undefined);
      customUrl = '';
      customName = '';
      await refreshDownloads();
      startPolling();
      toasts.add('Custom model download started', 'success');
    } catch (e) {
      customError = (e as Error).message;
    } finally {
      customDownloading = false;
    }
  }

  async function deleteCustom(key: string) {
    try {
      await removeCustomModel(key);
      downloads = downloads.filter((d) => d.key !== key);
      toasts.add('Custom model removed', 'success');
    } catch (e) {
      toasts.add((e as Error).message, 'error');
    }
  }

  function parseHfUrl(url: string): { repo: string; filename: string } | null {
    const match = url.match(/https?:\/\/huggingface\.co\/([^/]+)\/([^/]+)\/(?:resolve|blob)\/[^/]+\/(.+)/);
    if (!match) return null;
    return { repo: `${match[1]}/${match[2]}`, filename: match[3] };
  }

  function applyLlmSelection(id: string) {
    if (!id) return;
    const [provider, ...rest] = id.split(':');
    const model = rest.join(':');
    if (provider === 'local') {
      settings.provider = 'local';
      settings.default_llm = model;
      settings.local_model = model;
    } else {
      settings.provider = 'ollama';
      settings.default_llm = model;
      settings.ollama_model = model;
    }
  }

  function applyEmbeddingSelection(id: string) {
    if (!id) return;
    const [provider, ...rest] = id.split('|');
    const model = rest.join('|');
    settings.embedding_provider = provider as 'fastembed' | 'ollama' | 'local';
    settings.embedding_model = model;
  }

  function initSelections() {
    if (settings.provider === 'local' && settings.default_llm) {
      llmSelection = `local:${settings.default_llm}`;
    } else if (settings.ollama_model || settings.default_llm) {
      llmSelection = `ollama:${settings.default_llm || settings.ollama_model}`;
    }
    if (settings.embedding_provider && settings.embedding_model) {
      embeddingSelection = `${settings.embedding_provider}|${settings.embedding_model}`;
    }
  }

  onMount(async () => {
    const res = await getSettings();
    settings = res.settings;
    localStatus = await getLocalStatus().catch(() => null);
    catalog = await getCatalog().catch(() => null);
    syncDownloads(catalog?.downloads ?? []);
    initSelections();
    loading = false;
    if (hasActiveDownload) startPolling();
  });

  function applyTier(tier: 'low' | 'medium' | 'high') {
    settings.device_tier = tier;
    const llm = catalog?.llm?.[0];
    const rec = catalog?.embeddings?.[0];
    settings.provider = 'ollama';
    if (llm) {
      settings.default_llm = llm;
      settings.ollama_model = llm;
      llmSelection = `ollama:${llm}`;
    }
    if (rec) {
      settings.embedding_provider = rec.provider as 'fastembed' | 'ollama' | 'local';
      settings.embedding_model = rec.model;
      embeddingSelection = `${rec.provider}|${rec.model}`;
    }
  }

  function formatBytes(bytes: number) {
    if (!bytes) return '0 B';
    const units = ['B', 'KB', 'MB', 'GB'];
    let v = bytes;
    let i = 0;
    while (v >= 1024 && i < units.length - 1) {
      v /= 1024;
      i++;
    }
    return `${v.toFixed(1)} ${units[i]}`;
  }

  async function save() {
    saving = true;
    try {
      const payload = { ...settings };
      const n = Number(payload.max_concurrent_actions);
      payload.max_concurrent_actions =
        Number.isFinite(n) && n >= 1 ? Math.min(16, Math.round(n)) : 2;
      const res = await updateSettings(payload);
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
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium text-slate-700">Default LLM</label>
              <select bind:value={llmSelection} onchange={(e) => applyLlmSelection(e.currentTarget.value)} class="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm">
                <option value="">— Choose a model —</option>
                {#each chatGroups as group}
                  {#if chatOptions.some((o) => o.group === group)}
                    <optgroup label={group}>
                      {#each chatOptions.filter((o) => o.group === group) as opt}
                        <option value={opt.id}>{opt.name}</option>
                      {/each}
                    </optgroup>
                  {/if}
                {/each}
              </select>
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium text-slate-700">Embedding Provider</label>
              <select bind:value={embeddingSelection} onchange={(e) => applyEmbeddingSelection(e.currentTarget.value)} class="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm">
                <option value="">— Choose an embedding —</option>
                {#each embeddingOptions as opt}
                  <option value={opt.id}>{opt.provider} · {opt.model}</option>
                {/each}
              </select>
              <p class="mt-1 text-xs text-slate-400">
                {#if embeddingSelection}
                  {@const opt = embeddingOptions.find((o) => o.id === embeddingSelection)}
                  {opt?.note} ({opt?.dim ?? '?'}-dim)
                {/if}
              </p>
            </div>
          </div>

          {#if embeddingDownload && !embeddingDownload.downloaded}
            <div class="mt-3 rounded-lg border border-slate-200 p-3">
              <div class="flex items-center justify-between gap-3">
                <p class="text-sm text-slate-600">
                  The local embedding model <span class="font-medium">{embeddingDownload.name}</span> ({embeddingDownload.size_label}) needs to be downloaded.
                </p>
                <button type="button" onclick={() => download(embeddingDownload.key)} disabled={embeddingDownload.status === 'downloading'} class="shrink-0 rounded-lg bg-slate-800 px-4 py-1.5 text-sm font-medium text-white hover:bg-slate-900 disabled:opacity-50">
                  {embeddingDownload.status === 'downloading' ? 'Downloading…' : 'Download'}
                </button>
              </div>
              {#if embeddingDownload.status === 'downloading'}
                <div class="mt-2 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                  <div class="h-full rounded-full bg-indigo-600 transition-all" style="width: {embeddingDownload.progress}%"></div>
                </div>
                <p class="mt-1 text-xs text-slate-400">
                  {formatBytes(embeddingDownload.downloaded_bytes)} / {formatBytes(embeddingDownload.total_bytes)} ({embeddingDownload.progress}%)
                </p>
              {/if}
              {#if embeddingDownload.status === 'error'}
                <p class="mt-1 text-xs text-red-500">Download failed: {embeddingDownload.error}</p>
              {/if}
            </div>
          {/if}
        </section>

        <section>
          <h2 class="mb-3 text-lg font-semibold text-slate-800">Download a local model from HuggingFace</h2>
          <p class="mb-4 text-xs text-slate-400">
            No manual file placement — pick a model and it downloads into the app's models folder automatically. Chat models
            run via llama.cpp on your device.
          </p>
          <div class="space-y-3">
            {#if chatDownloads.length === 0}
              <p class="text-sm text-slate-400">All catalog chat models are installed.</p>
            {:else}
              {#each chatDownloads as dl}
                <div class="rounded-lg border border-slate-200 p-4">
                  <div class="flex items-center justify-between gap-3">
                    <div>
                      <p class="text-sm font-medium text-slate-800">{dl.name}</p>
                      <p class="text-xs text-slate-400">{dl.size_label} · {dl.note}</p>
                    </div>
                    <button type="button" onclick={() => download(dl.key)} disabled={dl.status === 'downloading'} class="shrink-0 rounded-lg bg-indigo-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50">
                      {dl.status === 'downloading' ? `Downloading… ${dl.progress}%` : `Download (${dl.size_label})`}
                    </button>
                  </div>
                  {#if dl.status === 'downloading'}
                    <div class="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                      <div class="h-full rounded-full bg-indigo-600 transition-all" style="width: {dl.progress}%"></div>
                    </div>
                    <p class="mt-1 text-xs text-slate-400">
                      {formatBytes(dl.downloaded_bytes)} / {formatBytes(dl.total_bytes)} ({dl.progress}%)
                    </p>
                  {/if}
                  {#if dl.status === 'error'}
                    <p class="mt-2 text-xs text-red-500">Download failed: {dl.error}</p>
                  {/if}
                </div>
              {/each}
            {/if}
          </div>
          {#if localStatus && localStatus.ollama_models.length > 0}
            <p class="mt-3 text-xs text-slate-400">Installed Ollama models: {localStatus.ollama_models.join(', ')}</p>
          {/if}
        </section>

        <section>
          <h2 class="mb-3 text-lg font-semibold text-slate-800">Add Custom Model from HuggingFace</h2>
          <p class="mb-4 text-xs text-slate-400">
            Paste a HuggingFace URL to download any GGUF model. Works on any PC with enough RAM — no GPU required.
          </p>
          <div class="space-y-3">
            <div>
              <label class="mb-1 block text-sm font-medium text-slate-700">HuggingFace URL</label>
              <input
                type="url"
                bind:value={customUrl}
                placeholder="https://huggingface.co/owner/repo/resolve/main/model.gguf"
                class="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm"
              />
              {#if parsedUrl}
                <p class="mt-1 text-xs text-slate-500">
                  Repo: <span class="font-medium">{parsedUrl.repo}</span> · File: <span class="font-medium">{parsedUrl.filename}</span>
                </p>
              {/if}
            </div>
            <div>
              <label class="mb-1 block text-sm font-medium text-slate-700">Display Name (optional)</label>
              <input
                type="text"
                bind:value={customName}
                placeholder="e.g. Mistral 7B Q4"
                class="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm"
              />
            </div>
            <button
              type="button"
              onclick={downloadCustom}
              disabled={!customUrl.trim() || customDownloading || !parsedUrl}
              class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {customDownloading ? 'Starting download...' : 'Download Custom Model'}
            </button>
            {#if customError}
              <p class="text-xs text-red-500">{customError}</p>
            {/if}
          </div>
        </section>

        {#if customModels.length > 0}
          <section>
            <h2 class="mb-3 text-lg font-semibold text-slate-800">Custom Models</h2>
            <div class="space-y-3">
              {#each customModels as cm}
                <div class="rounded-lg border border-slate-200 p-4">
                  <div class="flex items-center justify-between gap-3">
                    <div class="min-w-0 flex-1">
                      <p class="text-sm font-medium text-slate-800">{cm.name}</p>
                      <p class="text-xs text-slate-400">
                        {cm.size_label || 'Size unknown'}
                        {#if cm.ram_estimate_gb}
                          · Est. RAM: ~{cm.ram_estimate_gb} GB
                        {/if}
                      </p>
                      {#if cm.url}
                        <p class="mt-0.5 truncate text-[11px] text-slate-400">{cm.url}</p>
                      {/if}
                    </div>
                    <div class="flex items-center gap-2">
                      {#if cm.downloaded}
                        <span class="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">Installed</span>
                      {:else if cm.status === 'downloading'}
                        <span class="text-xs text-indigo-600">{cm.progress}%</span>
                      {:else}
                        <button
                          type="button"
                          onclick={() => download(cm.key)}
                          class="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700"
                        >
                          Download
                        </button>
                      {/if}
                      <button
                        type="button"
                        onclick={() => deleteCustom(cm.key)}
                        class="rounded px-2 py-1 text-xs text-slate-400 hover:text-red-500"
                        title="Remove model"
                      >
                        ✕
                      </button>
                    </div>
                  </div>
                  {#if cm.status === 'downloading'}
                    <div class="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-100">
                      <div class="h-full rounded-full bg-indigo-600 transition-all" style="width: {cm.progress}%"></div>
                    </div>
                    <p class="mt-1 text-xs text-slate-400">
                      {formatBytes(cm.downloaded_bytes)} / {formatBytes(cm.total_bytes)}
                    </p>
                  {/if}
                  {#if cm.status === 'error'}
                    <p class="mt-2 text-xs text-red-500">Download failed: {cm.error}</p>
                  {/if}
                </div>
              {/each}
            </div>
          </section>
        {/if}

        <section class="rounded-lg border border-amber-200 bg-amber-50 p-4">
          <h2 class="mb-2 text-lg font-semibold text-amber-800">Hardware Guide</h2>
          <p class="mb-3 text-xs text-amber-700">
            These models run on your CPU — no graphics card needed. Pick the right quantization level for your RAM.
          </p>
          <div class="space-y-2 text-xs text-amber-700">
            <div class="flex gap-3">
              <span class="w-16 font-medium">4 GB RAM</span>
              <span>Use Q2/Q3 quantized models under ~1.5 GB. Good for light tasks.</span>
            </div>
            <div class="flex gap-3">
              <span class="w-16 font-medium">8 GB RAM</span>
              <span>Use Q4/Q3 models up to ~4 GB. Solid for daily research use.</span>
            </div>
            <div class="flex gap-3">
              <span class="w-16 font-medium">16 GB RAM</span>
              <span>Use Q4/Q5 models up to ~8 GB. Best balance of speed and quality.</span>
            </div>
            <div class="flex gap-3">
              <span class="w-16 font-medium">32 GB+</span>
              <span>Use any model up to ~15 GB. Full quality with Q6/Q8/F16.</span>
            </div>
          </div>
          <p class="mt-3 text-[11px] text-amber-600">
            Tip: Q4 quantized models are the sweet spot for most users — good quality at half the RAM of full precision.
          </p>
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

        <section>
          <h2 class="mb-4 text-lg font-semibold text-slate-800">Background actions</h2>
          <div class="rounded-lg border border-slate-200 p-4">
            <div class="mb-2 flex flex-wrap items-center gap-3">
              <label for="max-concurrent-actions" class="text-sm font-medium text-slate-700">
                Run this many actions at once
              </label>
              <input
                id="max-concurrent-actions"
                type="number"
                min="1"
                max="16"
                bind:value={settings.max_concurrent_actions}
                class="w-24 rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-indigo-500"
              />
            </div>
            <p class="text-xs leading-relaxed text-amber-700">
              Actions include literature map builds and knowledge graph generations. The more
              actions run at once, the more processing power your PC uses — keep it low on
              low-end devices or while you need the machine for other work.
            </p>
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
