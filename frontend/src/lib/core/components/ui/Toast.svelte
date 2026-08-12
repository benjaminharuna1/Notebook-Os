<script lang="ts">
  import { toasts } from '$lib/core/stores/toasts';
  import { fade, slide } from 'svelte/transition';

  const colorMap = {
    success: 'bg-emerald-50 border-emerald-200 text-emerald-800',
    error: 'bg-red-50 border-red-200 text-red-800',
    info: 'bg-blue-50 border-blue-200 text-blue-800',
  };
</script>

{#each $toasts as toast (toast.id)}
  <div
    class="fixed bottom-4 right-4 z-50 rounded-lg border px-4 py-3 shadow-lg {colorMap[toast.type]}"
    transition={slide}
  >
    {toast.message}
  </div>
{/each}
