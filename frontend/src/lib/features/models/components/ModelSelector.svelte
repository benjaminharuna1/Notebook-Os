<script lang="ts">
  import { onMount } from 'svelte';
  import { listModels, switchModel } from '../api';
  import { availableModels, activeModel } from '../store';
  import type { ModelConfig } from '../types';

  let open = $state(false);

  onMount(async () => {
    try {
      const result = await listModels();
      availableModels.set(result.available);
      activeModel.set(result.active);
    } catch {
      /* backend not reachable; selector stays empty */
    }
  });

  async function handleSelect(model: ModelConfig) {
    try {
      await switchModel(model.id);
      activeModel.set(model);
    } catch {
      /* switching failed; keep previous selection */
    }
    open = false;
  }
</script>

<div class="relative">
  <button
    onclick={() => (open = !open)}
    class="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm"
  >
    {$activeModel?.name || 'Select Model'}
    <span class="text-xs text-slate-400">▾</span>
  </button>

  {#if open}
    <div class="absolute right-0 top-full z-50 mt-1 w-64 rounded-lg border border-slate-200 bg-white shadow-lg">
      {#if $availableModels.length === 0}
        <div class="px-4 py-3 text-sm text-slate-400">No models available yet.</div>
      {:else}
        {#each $availableModels as model (model.id)}
          <button
            onclick={() => handleSelect(model)}
            class="flex w-full items-center gap-2 px-4 py-2 text-left text-sm hover:bg-slate-50 {$activeModel?.id ===
            model.id
              ? 'bg-indigo-50 text-indigo-700'
              : 'text-slate-700'}"
          >
            <span class="flex-1">{model.name}</span>
            <span
              class="rounded px-1.5 py-0.5 text-[10px] font-medium uppercase {model.source === 'cloud'
                ? 'bg-violet-100 text-violet-700'
                : 'bg-emerald-100 text-emerald-700'}"
            >
              {model.source}
            </span>
          </button>
        {/each}
      {/if}
    </div>
  {/if}
</div>
