<script lang="ts">
  import { onMount } from 'svelte';
  import { listDocuments, deleteDocument } from '../api';
  import type { Document } from '../types';

  let docs: Document[] = $state([]);
  let total = $state(0);
  let page = $state(1);
  let loading = $state(true);

  onMount(async () => {
    await loadDocs();
  });

  async function loadDocs() {
    loading = true;
    const result = await listDocuments({ page });
    docs = result.documents;
    total = result.total;
    loading = false;
  }

  async function handleDelete(id: string) {
    await deleteDocument(id);
    await loadDocs();
  }

  const fileTypeColors: Record<string, string> = {
    pdf: 'bg-red-100 text-red-700',
    docx: 'bg-blue-100 text-blue-700',
    txt: 'bg-slate-100 text-slate-700',
  };
</script>

<div class="space-y-4">
  {#if loading}
    <div class="text-center text-slate-400">Loading...</div>
  {:else if docs.length === 0}
    <div class="text-center text-slate-400">No documents yet</div>
  {:else}
    {#each docs as doc (doc.id)}
      <div class="flex items-center gap-4 rounded-lg border border-slate-200 p-4">
        <span
          class="rounded px-2 py-0.5 text-xs font-medium {fileTypeColors[doc.file_type] || 'bg-slate-100 text-slate-700'}"
        >
          {doc.file_type}
        </span>
        <div class="flex-1">
          <a href="/library/{doc.id}" class="font-medium text-slate-900 hover:text-indigo-600">
            {doc.title}
          </a>
          <p class="text-xs text-slate-400">{doc.filename}</p>
        </div>
        <button
          onclick={() => handleDelete(doc.id)}
          class="text-xs text-red-500 hover:text-red-700"
        >
          Delete
        </button>
      </div>
    {/each}
  {/if}
</div>
