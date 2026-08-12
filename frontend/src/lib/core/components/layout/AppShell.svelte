<script lang="ts">
  import Sidebar from './Sidebar.svelte';
  import Toast from '$lib/core/components/ui/Toast.svelte';

  let { children }: { children?: import('svelte').Snippet } = $props();
</script>

<div class="flex h-screen bg-white">
  <Sidebar />
  <main class="flex-1 overflow-auto">
    {@render children?.()}
  </main>
</div>

<Toast />
