<script lang="ts">
  import { mount } from 'svelte';

  let { open = false, title = '', onclose, children }: {
    open?: boolean;
    title?: string;
    onclose?: () => void;
    children?: import('svelte').Snippet;
  } = $props();
</script>

{#if open}
  <div class="fixed inset-0 z-50 flex items-center justify-center">
    <div class="fixed inset-0 bg-black/50" onclick={onclose} />
    <div class="relative z-10 w-full max-w-lg rounded-xl bg-white p-6 shadow-xl">
      {#if title}
        <div class="mb-4 flex items-center justify-between">
          <h2 class="text-lg font-semibold">{title}</h2>
          <button onclick={onclose} class="text-slate-400 hover:text-slate-600">&times;</button>
        </div>
      {/if}
      {@render children?.()}
    </div>
  </div>
{/if}
