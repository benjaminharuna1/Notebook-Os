<script lang="ts">
  import { page } from '$app/stores';
  import { getDocument } from '$lib/features/documents/api';
  import type { Document } from '$lib/features/documents/types';

  const projectId = $derived($page.params.id);
  const docId = $derived($page.params.docId);

  let doc = $state<Document | null>(null);

  $effect(() => {
    doc = null;
    getDocument(docId)
      .then((d) => (doc = d))
      .catch(() => (doc = null));
  });
</script>

<div class="h-full overflow-auto p-6">
  <a href="/projects/{projectId}/library" class="text-sm font-medium text-indigo-600 hover:text-indigo-800">
    &larr; Back to Library
  </a>
  {#if doc}
    <h1 class="mt-2 mb-2 text-2xl font-bold text-slate-900">{doc.title}</h1>
    <p class="text-sm text-slate-400">{doc.filename} &middot; {doc.file_type}</p>
  {:else}
    <p class="mt-4 text-slate-400">Loading...</p>
  {/if}
</div>
