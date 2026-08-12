<script lang="ts">
  import { uploadQueue } from '../store';

  const items = $derived($uploadQueue);
</script>

{#if items.length > 0}
  <div class="space-y-2">
    {#each items as item (item.id)}
      <div class="flex items-center gap-3 rounded-lg border border-slate-200 p-3">
        <span class="flex-1 text-sm">{item.name}</span>
        {#if item.status === 'error'}
          <span class="text-xs text-red-500">{item.error}</span>
        {:else if item.status === 'done'}
          <span class="text-xs text-emerald-600">Done</span>
        {:else}
          <span class="text-xs text-slate-400">{item.status}...</span>
        {/if}
      </div>
    {/each}
  </div>
{/if}
