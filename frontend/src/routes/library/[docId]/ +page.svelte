<script lang="ts">
  import { page } from '$app/stores';
  import { onMount } from 'svelte';
  import { getDocument } from '$lib/features/documents/api';
  import type { Document } from '$lib/features/documents/types';
  import Header from '$lib/core/components/layout/Header.svelte';

  let doc = $state<Document | null>(null);

  onMount(async () => {
    doc = await getDocument($page.params.docId);
  });
</script>

<div class="flex h-full flex-col">
  <Header />
  <div class="flex-1 overflow-auto p-6">
    {#if doc}
      <h1 class="mb-2 text-2xl font-bold text-slate-900">{doc.title}</h1>
      <p class="mb-4 text-sm text-slate-400">{doc.filename} &middot; {doc.file_type}</p>
    {:else}
      <p class="text-slate-400">Loading...</p>
    {/if}
  </div>
</div>
