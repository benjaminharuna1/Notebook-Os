<script lang="ts">
  import { onMount } from 'svelte';
  import Sidebar from './Sidebar.svelte';
  import Toast from '$lib/core/components/ui/Toast.svelte';
  import ActionsDock from '$lib/features/actions/components/ActionsDock.svelte';
  import { startActionPolling, stopActionPolling } from '$lib/features/actions/store';

  let { children }: { children?: import('svelte').Snippet } = $props();

  onMount(() => {
    startActionPolling();
    return stopActionPolling;
  });
</script>

<div class="flex h-screen bg-white">
  <Sidebar />
  <main class="flex-1 overflow-auto">
    {@render children?.()}
  </main>
</div>

<ActionsDock />
<Toast />
