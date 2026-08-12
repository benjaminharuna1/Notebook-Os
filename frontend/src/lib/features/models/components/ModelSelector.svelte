<script lang="ts">
  import { onMount } from 'svelte';
  import { listModels, switchModel } from '../api';
  import { availableModels, activeModel } from '../store';
  import type { ModelConfig } from '../types';

  let open = $state(false);

  onMount(async () => {
    const result = await listModels();
    availableModels.set(result.available);
    activeModel.set(result.active);
  });

  async function handleSelect(model: ModelConfig) {
    await switchModel(model.id);
    activeModel.set(model);
    open = false;
  }
</script>

<div class="relative">
  <button
    onclick={() => (open = !open)}
    class="flex items-center gap-2 rounded-lg border border-slate-200 px-3 py-2 text-sm"
  >
    {$activeModel?.name || 'Select Model'}
  </button>

  {#if open}
    <div class="absolute right-0 top-full z-50 mt-1 w-56 rounded-lg border border-slate-200 bg-white shadow-lg">
      {#each $availableModels as model (model.id)}
        <button
          onclick={() => handleSelect(model)}
          class="flex w-full items-center gap-2 px-4 py-2 text-left text-sm hover:bg-slate-50 {$activeModel?.id ===
          model.id
            ? 'bg-indigo-50 text-indigo-700'
            : 'text-slate-700'}"
        >
          <span class="flex-1">{model.name}</span>
          <span class="text-xs text-slate-400">{model.provider}</span>
        </button>
      {/each}
    </div>
  {/if}
</div>
