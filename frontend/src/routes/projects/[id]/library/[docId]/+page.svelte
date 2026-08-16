<script lang="ts">
  import { page } from '$app/stores';
  import { getDocument } from '$lib/features/documents/api';
  import PdfViewer from '$lib/features/documents/components/PdfViewer.svelte';
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

<div class="flex h-full flex-col">
  <div class="flex items-center gap-3 border-b border-slate-200 px-6 py-3">
    <a
      href="/projects/{projectId}/library"
      class="text-sm font-medium text-indigo-600 hover:text-indigo-800"
    >
      &larr; Back to Library
    </a>
    <div class="min-w-0 flex-1">
      {#if doc}
        <h1 class="truncate text-lg font-bold text-slate-900">{doc.title}</h1>
        <p class="truncate text-xs text-slate-400">{doc.filename} &middot; {doc.file_type}</p>
      {:else}
        <p class="text-sm text-slate-400">Loading document info…</p>
      {/if}
    </div>
  </div>
  <div class="min-h-0 flex-1 p-4">
    <PdfViewer
      projectId={projectId}
      documentId={docId}
      title={doc?.title ?? 'Document preview'}
      fileType={doc?.file_type ?? 'pdf'}
    />
  </div>
</div>
