<script lang="ts">
  import StatusBadge from '$lib/core/components/StatusBadge.svelte';
  import { listDocuments, deleteDocuments } from '../api';
  import { pauseIngestion, resumeIngestion, reprocessIngestion, reprocessDocuments } from '$lib/features/ingestion/api';
  import {
    exportReferencesDocx,
    getLiteratureJob,
    regenerateLiteratureMetadata,
    startLiteratureBuild,
    type LiteratureBuildJob,
  } from '$lib/features/literature/api';
  import type { Document } from '../types';

  let { projectId }: { projectId?: string } = $props();

  let docs: Document[] = $state([]);
  let total = $state(0);
  let page = $state(1);
  let loading = $state(true);

  let selected = $state<Set<string>>(new Set());
  let openMenu = $state<string | null>(null);
  let busy = $state<string | null>(null);
  let exporting = $state(false);
  let actionError = $state('');
  let actionInfo = $state('');
  let buildJob = $state<LiteratureBuildJob | null>(null);
  let buildToken = $state(0);

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

  $effect(() => {
    if (!openMenu) return;
    function onDocClick() {
      openMenu = null;
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') openMenu = null;
    }
    document.addEventListener('click', onDocClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('click', onDocClick);
      document.removeEventListener('keydown', onKey);
    };
  });

  function clearActionFeedback() {
    actionError = '';
    actionInfo = '';
  }

  async function trackBuild(job: LiteratureBuildJob) {
    if (!projectId) return;
    const token = ++buildToken;
    buildJob = { ...job };
    while (true) {
      await new Promise((r) => setTimeout(r, 1000));
      if (token !== buildToken) return;
      const current = await getLiteratureJob(projectId, job.id);
      if (token !== buildToken) return;
      buildJob = { ...current };
      if (current.status === 'done') {
        buildJob = null;
        actionInfo = 'Literature mapping built successfully.';
        return;
      }
      if (current.status === 'error') {
        buildJob = null;
        throw new Error(current.error ?? 'Literature map build failed');
      }
    }
  }

  async function runBatch(label: string, action: () => Promise<void>) {
    if (selected.size === 0) return;
    busy = label;
    clearActionFeedback();
    try {
      await action();
      selected = new Set();
    } catch (e) {
      actionError = e instanceof Error ? e.message : String(e ?? 'Action failed');
    } finally {
      busy = null;
      buildToken += 1;
      buildJob = null;
      await loadDocs();
    }
  }

  function toggleSelect(id: string) {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    selected = next;
  }

  function toggleSelectAll() {
    if (selected.size === docs.length) selected = new Set();
    else selected = new Set(docs.map((d) => d.id));
  }

  async function handleBatchDelete() {
    if (!projectId) return;
    const ok = confirm(`Delete ${selected.size} paper(s)? This cannot be undone.`);
    if (!ok) return;
    await runBatch('delete', async () => {
      const result = await deleteDocuments(projectId, [...selected]);
      actionInfo = `Deleted ${result.deleted} paper(s).`;
    });
  }

  async function handleBatchReprocess() {
    await runBatch('reprocess', async () => {
      const result = await reprocessDocuments([...selected]);
      const message = `Requeued ${result.processed} paper(s).`;
      actionInfo = result.errors?.length
        ? `${message} ${result.errors.length} could not be reprocessed.`
        : message;
    });
  }

  async function handleBatchRegenerateMetadata() {
    if (!projectId) return;
    await runBatch('meta', async () => {
      const result = await regenerateLiteratureMetadata(projectId, [...selected]);
      actionInfo = `Processed metadata for ${result.processed} paper(s).`;
    });
  }

  async function handleBatchGenerateMapping() {
    if (!projectId) return;
    await runBatch('mapping', async () => {
      const job = await startLiteratureBuild(projectId);
      actionInfo = 'Building literature mapping…';
      await trackBuild(job);
    });
  }

  async function runDocAction(
    doc: Document,
    label: string,
    action: () => Promise<void>,
  ) {
    busy = label;
    openMenu = null;
    clearActionFeedback();
    try {
      await action();
    } catch (e) {
      actionError = e instanceof Error ? e.message : String(e ?? 'Action failed');
    } finally {
      busy = null;
      buildToken += 1;
      buildJob = null;
      await loadDocs();
    }
  }

  async function handleProcessMetadata(doc: Document) {
    if (!projectId) return;
    await runDocAction(doc, `meta:${doc.id}`, async () => {
      await regenerateLiteratureMetadata(projectId, [doc.id]);
      actionInfo = `Metadata processed for "${doc.title}".`;
    });
  }

  async function handleBuildMapping(doc: Document) {
    if (!projectId) return;
    await runDocAction(doc, `mapping:${doc.id}`, async () => {
      await regenerateLiteratureMetadata(projectId, [doc.id]);
      const job = await startLiteratureBuild(projectId);
      actionInfo = `Building literature mapping for "${doc.title}"…`;
      await trackBuild(job);
    });
  }

  async function handleExportReferences() {
    if (!projectId) return;
    exporting = true;
    clearActionFeedback();
    try {
      await exportReferencesDocx(projectId);
    } catch (e) {
      actionError = e instanceof Error ? e.message : String(e ?? 'Export failed');
    } finally {
      exporting = false;
    }
  }

  async function handleDelete(doc: Document) {
    const ok = confirm(`Delete "${doc.title}"? This cannot be undone.`);
    if (!ok) return;
    await runDocAction(doc, `delete:${doc.id}`, async () => {
      await deleteDocuments(projectId ?? '', [doc.id]);
      actionInfo = `Deleted "${doc.title}".`;
    });
  }

  async function handlePause(doc: Document) {
    await runDocAction(doc, `pause:${doc.id}`, async () => {
      await pauseIngestion(doc.id);
      doc.status = 'paused';
    });
  }

  async function handleResume(doc: Document) {
    await runDocAction(doc, `resume:${doc.id}`, async () => {
      await resumeIngestion(doc.id);
      doc.status = 'processing';
    });
  }

  async function handleReprocess(doc: Document) {
    await runDocAction(doc, `reprocess:${doc.id}`, async () => {
      await reprocessIngestion(doc.id);
      doc.status = 'queued';
    });
  }

  const fileTypeColors: Record<string, string> = {
    pdf: 'bg-red-100 text-red-700',
    docx: 'bg-blue-100 text-blue-700',
    txt: 'bg-slate-100 text-slate-700',
  };

  const allSelected = $derived(docs.length > 0 && selected.size === docs.length);
</script>

<div class="space-y-4">
  <div class="flex flex-wrap items-center justify-between gap-3">
    <h2 class="text-sm font-semibold text-slate-700">Papers ({total})</h2>
    <button
      onclick={handleExportReferences}
      disabled={exporting}
      class="rounded-lg border border-slate-300 px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-50"
    >
      {exporting ? 'Exporting…' : '⬇ Export APA references (.docx)'}
    </button>
  </div>

  {#if actionError}
    <p class="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
      {actionError}
    </p>
  {/if}
  {#if actionInfo}
    <p class="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
      {actionInfo}
    </p>
  {/if}

  {#if buildJob}
    <div class="rounded-lg border border-indigo-200 bg-indigo-50 p-3">
      <div class="mb-1 flex items-center justify-between text-xs text-indigo-700">
        <span>{buildJob.stage ?? 'Building literature mapping'}</span>
        <span>{buildJob.progress ?? 0}%</span>
      </div>
      <div class="h-2 overflow-hidden rounded-full bg-indigo-100">
        <div
          class="h-full rounded-full bg-indigo-600 transition-all"
          style="width: {Math.min(100, Math.max(0, buildJob.progress ?? 0))}%"
        ></div>
      </div>
    </div>
  {/if}

  {#if selected.size > 0}
    <div class="flex flex-wrap items-center gap-2 rounded-xl border border-indigo-200 bg-indigo-50 p-3">
      <span class="text-xs font-semibold text-indigo-800">{selected.size} selected</span>
      <div class="flex flex-wrap gap-2">
        <button
          onclick={handleBatchDelete}
          disabled={busy !== null}
          class="rounded-lg border border-red-300 bg-white px-3 py-1.5 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
        >
          {busy === 'delete' ? 'Deleting…' : 'Delete'}
        </button>
        <button
          onclick={handleBatchReprocess}
          disabled={busy !== null}
          class="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-50"
        >
          {busy === 'reprocess' ? 'Reprocessing…' : 'Reprocess'}
        </button>
        <button
          onclick={handleBatchRegenerateMetadata}
          disabled={busy !== null}
          class="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-50"
        >
          {busy === 'meta' ? 'Processing…' : 'Regenerate metadata'}
        </button>
        <button
          onclick={handleBatchGenerateMapping}
          disabled={busy !== null}
          class="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
        >
          {busy === 'mapping' ? 'Building…' : 'Generate literature mapping'}
        </button>
        <button
          onclick={() => (selected = new Set())}
          disabled={busy !== null}
          class="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-medium text-slate-500 hover:bg-slate-100 disabled:opacity-50"
        >
          Clear
        </button>
      </div>
    </div>
  {/if}

  {#if loading}
    <div class="text-center text-slate-400">Loading...</div>
  {:else if docs.length === 0}
    <div class="text-center text-slate-400">No documents yet</div>
  {:else}
    <div class="rounded-lg border border-slate-200">
      <div class="flex items-center gap-4 border-b border-slate-200 bg-slate-50 px-4 py-2">
        <input
          type="checkbox"
          checked={allSelected}
          onchange={toggleSelectAll}
          class="h-4 w-4 accent-indigo-600"
          aria-label="Select all papers"
        />
        <span class="text-xs font-semibold text-slate-500">Paper</span>
        <span class="flex-1"></span>
        <span class="w-24 text-right text-xs font-semibold text-slate-500">Status</span>
        <span class="w-10"></span>
      </div>
      {#each docs as doc (doc.id)}
        <div class="relative flex items-center gap-4 border-b border-slate-100 px-4 py-3 last:border-b-0">
          <input
            type="checkbox"
            checked={selected.has(doc.id)}
            onchange={() => toggleSelect(doc.id)}
            class="h-4 w-4 accent-indigo-600"
            aria-label={`Select ${doc.title}`}
          />
          <span
            class="rounded px-2 py-0.5 text-xs font-medium {fileTypeColors[doc.file_type] || 'bg-slate-100 text-slate-700'}"
          >
            {doc.file_type}
          </span>
          <div class="min-w-0 flex-1">
            <a
              href={projectId ? `/projects/${projectId}/library/${doc.id}` : `/library/${doc.id}`}
              class="font-medium text-slate-900 hover:text-indigo-600"
            >
              {doc.title}
            </a>
            <p class="truncate text-xs text-slate-400">{doc.filename}</p>
          </div>
          <StatusBadge status={doc.status} />

          <div class="relative w-10">
            <button
              onclick={(e) => {
                e.stopPropagation();
                openMenu = openMenu === doc.id ? null : doc.id;
              }}
              disabled={busy !== null}
              class="rounded-md p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-700 disabled:opacity-50"
              aria-label={`Actions for ${doc.title}`}
              aria-expanded={openMenu === doc.id}
              title="Actions"
            >
              <span class="text-lg leading-none">⋮</span>
            </button>
            {#if openMenu === doc.id}
              <div
                class="absolute right-0 top-full z-10 mt-1 w-52 overflow-hidden rounded-xl border border-slate-200 bg-white py-1 shadow-lg"
              >
                {#if doc.status === 'queued' || doc.status === 'processing'}
                  <button
                    onclick={() => handlePause(doc)}
                    disabled={busy !== null}
                    class="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-amber-600 hover:bg-slate-50 disabled:opacity-50"
                  >
                    ⏸ Pause
                  </button>
                {:else if doc.status === 'paused'}
                  <button
                    onclick={() => handleResume(doc)}
                    disabled={busy !== null}
                    class="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-indigo-600 hover:bg-slate-50 disabled:opacity-50"
                  >
                    ▶ Continue
                  </button>
                {:else}
                  <button
                    onclick={() => handleReprocess(doc)}
                    disabled={busy !== null}
                    class="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-slate-600 hover:bg-slate-50 disabled:opacity-50"
                  >
                    ↻ Reprocess
                  </button>
                {/if}
                <button
                  onclick={() => handleProcessMetadata(doc)}
                  disabled={busy !== null}
                  class="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-indigo-600 hover:bg-slate-50 disabled:opacity-50"
                >
                  ✎ Process metadata
                </button>
                <button
                  onclick={() => handleBuildMapping(doc)}
                  disabled={busy !== null}
                  class="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-emerald-600 hover:bg-slate-50 disabled:opacity-50"
                >
                  🗺 Build mapping
                </button>
                <div class="my-1 border-t border-slate-100"></div>
                <button
                  onclick={() => handleDelete(doc)}
                  disabled={busy !== null}
                  class="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-red-600 hover:bg-red-50 disabled:opacity-50"
                >
                  🗑 Delete
                </button>
              </div>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
