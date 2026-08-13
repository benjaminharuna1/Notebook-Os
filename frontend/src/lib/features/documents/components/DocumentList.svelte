<script lang="ts">
  import StatusBadge from '$lib/core/components/StatusBadge.svelte';
  import { listDocuments, deleteDocument } from '../api';
  import { pauseIngestion, resumeIngestion, reprocessIngestion } from '$lib/features/ingestion/api';
  import type { Document } from '../types';

  let { projectId }: { projectId?: string } = $props();

  let docs: Document[] = $state([]);
  let total = $state(0);
  let page = $state(1);
  let loading = $state(true);

  const ACTIVE = ['queued', 'processing', 'paused'];

  async function loadDocs() {
    const result = await listDocuments({ page, project_id: projectId });
    docs = result.documents;
    total = result.total;
    loading = false;
  }

  $effect(() => {
    loadDocs();
    const timer = setInterval(() => loadDocs(), 2500);
    return () => clearInterval(timer);
  });

  async function handleDelete(id: string) {
    await deleteDocument(id);
    await loadDocs();
  }

  async function handlePause(doc: Document) {
    await pauseIngestion(doc.id);
    doc.status = 'paused';
  }

  async function handleResume(doc: Document) {
    await resumeIngestion(doc.id);
    doc.status = 'processing';
  }

  async function handleReprocess(doc: Document) {
    await reprocessIngestion(doc.id);
    doc.status = 'queued';
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
        <div class="min-w-0 flex-1">
          <a href="/library/{doc.id}" class="font-medium text-slate-900 hover:text-indigo-600">
            {doc.title}
          </a>
          <p class="truncate text-xs text-slate-400">{doc.filename}</p>
        </div>
        <StatusBadge status={doc.status} />
        <div class="flex items-center gap-2">
          {#if doc.status === 'queued' || doc.status === 'processing'}
            <button
              onclick={() => handlePause(doc)}
              class="text-xs text-amber-600 hover:text-amber-700"
              title="Pause"
            >
              ⏸ Pause
            </button>
          {:else if doc.status === 'paused'}
            <button
              onclick={() => handleResume(doc)}
              class="text-xs text-indigo-600 hover:text-indigo-700"
              title="Resume"
            >
              ▶ Continue
            </button>
          {:else}
            <button
              onclick={() => handleReprocess(doc)}
              class="text-xs text-slate-500 hover:text-slate-700"
              title="Reprocess"
            >
              ↻ Reprocess
            </button>
          {/if}
          <button
            onclick={() => handleDelete(doc.id)}
            class="text-xs text-red-500 hover:text-red-700"
            title="Delete"
          >
            Delete
          </button>
        </div>
      </div>
    {/each}
  {/if}
</div>
