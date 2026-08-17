<script lang="ts">
  import StatusBadge from '$lib/core/components/StatusBadge.svelte';
  import { listDocuments, deleteDocuments } from '../api';
  import { pauseIngestion, resumeIngestion, reprocessIngestion, reprocessDocuments } from '$lib/features/ingestion/api';
  import {
    exportReferencesDocx,
    getLiteratureEntry,
    getLiteratureJob,
    getLiteratureStatus,
    getPaperMetadata,
    updatePaperMetadata,
    applyPaperCandidate,
    regenerateLiteratureMetadata,
    startLiteratureBuild,
    type LiteratureBuildJob,
    type LiteratureEntry,
  } from '$lib/features/literature/api';
  import type { LiteratureMetadata, MetadataCandidate } from '$lib/features/literature/api';
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
  let systemWarnings = $state<string[]>([]);

  let viewPaper = $state<Document | null>(null);
  let viewEntry = $state<LiteratureEntry | null>(null);
  let viewLoading = $state(false);
  let viewEmpty = $state(false);
  let viewError = $state('');

  let metaModal = $state<{
    paperId: string;
    title: string;
    authorsText: string;
    year: string;
    doi: string;
    abstract: string;
    journal: string;
    volume: string;
    issue: string;
    pages: string;
    publisher: string;
    url: string;
    apaReference: string;
    fileType: string;
    paperType: string;
    edition: string;
    issn: string;
    isbn: string;
    candidates: MetadataCandidate[];
  } | null>(null);
  let metaLoading = $state(false);
  let metaSaving = $state(false);
  let metaError = $state('');
  let applyingCandidate = $state<number | null>(null);

  const entryFields = $derived(
    viewEntry
      ? [
          { label: 'Research Objective / Questions', value: viewEntry.research_objective },
          { label: 'Methodology & Sample', value: viewEntry.methodology },
          { label: 'Key Findings', value: viewEntry.key_findings },
          { label: 'Limitations & Gaps', value: viewEntry.limitations },
          { label: 'Relevance / Contribution', value: viewEntry.relevance },
        ]
      : [],
  );

  async function loadDocs() {
    const result = await listDocuments({ page, project_id: projectId });
    docs = result.documents;
    total = result.total;
    loading = false;
  }

  async function loadStatus() {
    if (!projectId) return;
    try {
      const status = await getLiteratureStatus(projectId);
      systemWarnings = status.warnings ?? [];
    } catch {
      systemWarnings = [];
    }
  }

  $effect(() => {
    loadDocs();
    loadStatus();
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

  async function openMetaModal(doc: Document) {
    if (!projectId || metaModal) return;
    metaModal = null;
    metaLoading = true;
    metaError = '';
    openMenu = null;
    try {
      const meta = await getPaperMetadata(projectId, doc.id);
      metaModal = {
        paperId: doc.id,
        title: meta.title ?? '',
        authorsText: (meta.authors ?? []).join('; '),
        year: meta.year != null ? String(meta.year) : '',
        doi: meta.doi ?? '',
        abstract: meta.abstract ?? '',
        journal: meta.journal ?? '',
        volume: meta.volume ?? '',
        issue: meta.issue ?? '',
        pages: meta.pages ?? '',
        publisher: meta.publisher ?? '',
        url: meta.url ?? '',
        apaReference: meta.apa_reference ?? '',
        fileType: meta.file_type ?? 'pdf',
        paperType: meta.paper_type ?? '',
        edition: meta.edition ?? '',
        issn: meta.issn ?? '',
        isbn: meta.isbn ?? '',
        candidates: meta.candidates ?? [],
      };
    } catch (e) {
      metaError = e instanceof Error ? e.message : String(e ?? 'Could not load metadata');
    } finally {
      metaLoading = false;
    }
  }

  async function applyCandidate(index: number) {
    if (!projectId || !metaModal) return;
    applyingCandidate = index;
    metaError = '';
    try {
      const meta = await applyPaperCandidate(projectId, metaModal.paperId, index);
      metaModal = {
        ...metaModal,
        title: meta.title ?? '',
        authorsText: (meta.authors ?? []).join('; '),
        year: meta.year != null ? String(meta.year) : '',
        doi: meta.doi ?? '',
        abstract: meta.abstract ?? '',
        journal: meta.journal ?? '',
        volume: meta.volume ?? '',
        issue: meta.issue ?? '',
        pages: meta.pages ?? '',
        publisher: meta.publisher ?? '',
        url: meta.url ?? '',
        apaReference: meta.apa_reference ?? '',
        paperType: meta.paper_type ?? '',
        edition: meta.edition ?? '',
        issn: meta.issn ?? '',
        isbn: meta.isbn ?? '',
        candidates: meta.candidates ?? [],
      };
      const paperId = metaModal.paperId;
      metaModal = null;
      await loadDocs();
      actionInfo = 'Metadata updated.';
    } catch (e) {
      metaError = e instanceof Error ? e.message : String(e ?? 'Could not apply metadata');
    } finally {
      applyingCandidate = null;
    }
  }

  async function saveMeta() {
    if (!projectId || !metaModal) return;
    metaSaving = true;
    metaError = '';
    try {
      const authors = metaModal.authorsText
        .split(';')
        .map((s) => s.trim())
        .filter(Boolean);
      const year = metaModal.year.trim() ? Number(metaModal.year.trim()) : null;
      await updatePaperMetadata(projectId, metaModal.paperId, {
        title: metaModal.title,
        authors,
        year: year && Number.isFinite(year) ? year : null,
        doi: metaModal.doi,
        abstract: metaModal.abstract,
        journal: metaModal.journal,
        volume: metaModal.volume,
        issue: metaModal.issue,
        pages: metaModal.pages,
        publisher: metaModal.publisher,
        url: metaModal.url,
        paper_type: metaModal.paperType || null,
        edition: metaModal.edition || null,
        issn: metaModal.issn || null,
        isbn: metaModal.isbn || null,
      });
      metaModal = null;
      await loadDocs();
      actionInfo = 'Metadata saved.';
    } catch (e) {
      metaError = e instanceof Error ? e.message : String(e ?? 'Save failed');
    } finally {
      metaSaving = false;
    }
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

  async function openView(doc: Document) {
    if (!projectId) return;
    viewPaper = doc;
    viewEntry = null;
    viewEmpty = false;
    viewError = '';
    viewLoading = true;
    openMenu = null;
    try {
      viewEntry = await getLiteratureEntry(projectId, doc.id);
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e ?? 'Could not load mapping');
      if (/no literature mapping/i.test(message)) {
        viewEmpty = true;
      } else {
        viewError = message;
      }
    } finally {
      viewLoading = false;
    }
  }

  $effect(() => {
    if (!viewPaper) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') viewPaper = null;
    }
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  });

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

  {#if systemWarnings.length > 0}
    <div class="space-y-2">
      {#each systemWarnings as warning}
        <div class="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          <span class="mt-0.5 shrink-0 text-sm">⚠</span>
          <span>{warning}</span>
        </div>
      {/each}
    </div>
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
                  onclick={() => openMetaModal(doc)}
                  disabled={busy !== null}
                  class="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-indigo-600 hover:bg-slate-50 disabled:opacity-50"
                >
                  ✏ Edit metadata
                </button>
                <button
                  onclick={() => openView(doc)}
                  class="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-slate-600 hover:bg-slate-50"
                >
                  📖 View mapping
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

{#if viewPaper}
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-sm"
  >
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Literature mapping"
      class="flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl"
    >
      <div class="flex items-start justify-between gap-4 border-b border-slate-100 px-6 py-4">
        <div class="min-w-0">
          <p class="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
            Literature mapping
          </p>
          <h3 class="mt-0.5 line-clamp-2 text-sm font-semibold text-slate-800">
            {viewPaper.title}
          </h3>
          {#if viewEntry?.citation}
            <p class="mt-1 text-xs text-slate-500">{viewEntry.citation}</p>
          {/if}
        </div>
        <button
          onclick={() => (viewPaper = null)}
          class="rounded-lg p-1.5 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600"
          aria-label="Close"
        >
          ✕
        </button>
      </div>

      <div class="flex-1 overflow-y-auto px-6 py-5">
        {#if viewLoading}
          <div class="flex items-center justify-center py-16 text-sm text-slate-400">
            Loading mapping…
          </div>
        {:else if viewError}
          <div class="py-10 text-center">
            <p class="text-sm text-red-600">{viewError}</p>
            <button
              onclick={() => {
                const doc = viewPaper;
                viewPaper = null;
                handleBuildMapping(doc);
              }}
              class="mt-4 rounded-lg border border-emerald-600 px-4 py-2 text-xs font-semibold text-emerald-600 transition hover:bg-emerald-50"
            >
              Try building the mapping
            </button>
          </div>
        {:else if viewEmpty}
          <div class="py-10 text-center">
            <p class="text-sm text-slate-500">
              No literature mapping yet for this paper.
            </p>
            <p class="mt-1 text-xs text-slate-400">
              Use “Build mapping” to generate the entry, then come back here to view it.
            </p>
            <button
              onclick={() => {
                const doc = viewPaper;
                viewPaper = null;
                handleBuildMapping(doc);
              }}
              class="mt-4 rounded-lg border border-emerald-600 px-4 py-2 text-xs font-semibold text-emerald-600 transition hover:bg-emerald-50"
            >
              🗺 Build mapping
            </button>
          </div>
        {:else if viewEntry}
          <div class="space-y-5">
            {#each entryFields as field}
              <div>
                <p class="text-[11px] font-semibold uppercase tracking-wide text-indigo-600">
                  {field.label}
                </p>
                <p class="mt-1 whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
                  {field.value || '—'}
                </p>
              </div>
            {/each}
            {#if viewEntry.apa_reference}
              <div class="rounded-xl border border-slate-100 bg-slate-50 px-4 py-3">
                <p class="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                  APA reference
                </p>
                <p class="mt-1 text-xs leading-relaxed text-slate-600">
                  {viewEntry.apa_reference}
                </p>
              </div>
            {/if}
          </div>
        {/if}
      </div>

      <div class="flex items-center justify-between border-t border-slate-100 px-6 py-3">
        {#if viewEntry?.auto_generated}
          <span class="text-[11px] italic text-slate-400">
            Auto-generated — review for accuracy
          </span>
        {:else}
          <span></span>
        {/if}
        <a
          href={`/projects/${projectId}/literature`}
          class="rounded-lg px-3 py-1.5 text-xs font-semibold text-indigo-600 transition hover:bg-indigo-50"
        >
          Open in Literature Map →
        </a>
      </div>
    </div>
  </div>
{/if}

{#if metaModal}
  <div class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-sm">
    <div class="flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
      <div class="flex items-center justify-between border-b border-slate-200 px-5 py-3">
        <h2 class="text-base font-semibold text-slate-900">Edit paper metadata</h2>
        <button
          onclick={() => (metaModal = null)}
          class="text-slate-400 hover:text-slate-700"
          aria-label="Close"
        >✕</button>
      </div>
      {#if metaLoading}
        <p class="p-6 text-sm text-slate-400">Loading metadata…</p>
      {:else}
        <div class="space-y-3 overflow-y-auto p-5">
          {#if metaError}
            <p class="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
              {metaError}
            </p>
          {/if}
          <div>
            <label class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">
              Document Type
            </label>
            <select
              bind:value={metaModal.paperType}
              class="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-indigo-500"
            >
              <option value="">Auto-detect</option>
              <option value="journal_article">Journal Article</option>
              <option value="conference_paper">Conference Paper</option>
              <option value="textbook">Textbook / Book</option>
              <option value="preprint">Preprint</option>
              <option value="thesis">Thesis / Dissertation</option>
              <option value="newspaper">Newspaper / Magazine</option>
              <option value="other">Other</option>
            </select>
          </div>
          <div>
            <label class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">
              Title
            </label>
            <input
              bind:value={metaModal.title}
              class="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-indigo-500"
            />
          </div>
          <div>
            <label class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">
              Authors
            </label>
            <input
              bind:value={metaModal.authorsText}
              placeholder="Family, Given; Family, Given"
              class="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-indigo-500"
            />
          </div>
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                Year
              </label>
              <input
                bind:value={metaModal.year}
                inputmode="numeric"
                placeholder="2021"
                class="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-indigo-500"
              />
            </div>
            {#if metaModal.paperType !== 'textbook'}
              <div>
                <label class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                  DOI
                </label>
                <input
                  bind:value={metaModal.doi}
                  placeholder="10.1000/xyz123"
                  class="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-indigo-500"
                />
              </div>
            {/if}
          </div>
          {#if metaModal.paperType === 'textbook'}
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Edition
                </label>
                <input
                  bind:value={metaModal.edition}
                  placeholder="3rd"
                  class="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                  ISBN
                </label>
                <input
                  bind:value={metaModal.isbn}
                  placeholder="978-0-123456-78-9"
                  class="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-indigo-500"
                />
              </div>
            </div>
          {/if}
          <div>
            <label class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">
              {metaModal.paperType === 'newspaper' ? 'Newspaper Name' : 'Journal / Container'}
            </label>
            <input
              bind:value={metaModal.journal}
              placeholder={metaModal.paperType === 'newspaper' ? 'The Guardian' : 'Journal of Example Research'}
              class="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-indigo-500"
            />
          </div>
          {#if metaModal.paperType === 'journal_article' || metaModal.paperType === 'conference_paper'}
            <div class="grid grid-cols-3 gap-3">
              <div>
                <label class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Volume
                </label>
                <input
                  bind:value={metaModal.volume}
                  placeholder="15"
                  class="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Issue
                </label>
                <input
                  bind:value={metaModal.issue}
                  placeholder="2"
                  class="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Pages
                </label>
                <input
                  bind:value={metaModal.pages}
                  placeholder="12-34"
                  class="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-indigo-500"
                />
              </div>
            </div>
            <div class="mt-3">
              <label class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                ISSN
              </label>
              <input
                bind:value={metaModal.issn}
                placeholder="1234-5678"
                class="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-indigo-500"
              />
            </div>
          {:else if metaModal.paperType === 'newspaper'}
            <div>
              <label class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                Pages
              </label>
              <input
                bind:value={metaModal.pages}
                placeholder="A1, A4"
                class="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-indigo-500"
              />
            </div>
          {:else if !metaModal.paperType || metaModal.paperType === 'other' || metaModal.paperType === 'preprint' || metaModal.paperType === 'thesis'}
            <div class="grid grid-cols-2 gap-3">
              <div>
                <label class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Volume
                </label>
                <input
                  bind:value={metaModal.volume}
                  placeholder="15"
                  class="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-indigo-500"
                />
              </div>
              <div>
                <label class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Issue
                </label>
                <input
                  bind:value={metaModal.issue}
                  placeholder="2"
                  class="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-indigo-500"
                />
              </div>
            </div>
          {/if}
          <div class="grid grid-cols-2 gap-3">
            <div>
              <label class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                Publisher
              </label>
              <input
                bind:value={metaModal.publisher}
                placeholder="Example Publishing"
                class="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-indigo-500"
              />
            </div>
            {#if metaModal.paperType !== 'textbook'}
              <div>
                <label class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Link / URL
                </label>
                <input
                  bind:value={metaModal.url}
                  placeholder="https://..."
                  class="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-indigo-500"
                />
              </div>
            {/if}
          </div>
          <div>
            <label class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">
              Abstract
            </label>
            <textarea
              bind:value={metaModal.abstract}
              rows="4"
              class="w-full resize-y rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-indigo-500"
            ></textarea>
          </div>
          <div class="rounded-lg bg-slate-50 px-3 py-2">
            <p class="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              APA reference (regenerated from these fields)
            </p>
            <p class="mt-1 break-words text-xs leading-snug text-slate-700">
              {metaModal.apaReference}
            </p>
          </div>
          {#if (metaModal.candidates ?? []).length > 0}
            <div class="rounded-xl border border-amber-200 bg-amber-50 p-3">
              <p class="text-[10px] font-semibold uppercase tracking-wider text-amber-700">
                Unverified paper — suggested records
              </p>
              <p class="mt-0.5 text-xs text-amber-700/80">
                Pick a record to apply it as the verified metadata.
              </p>
              <div class="mt-2 space-y-2">
                {#each metaModal.candidates as candidate, i (i)}
                  <div class="flex items-start gap-3 rounded-lg border border-amber-200 bg-white p-2.5">
                    <div class="min-w-0 flex-1">
                      <p class="truncate text-sm font-medium text-slate-900">
                        {candidate.title ?? 'Untitled'}
                      </p>
                      <p class="mt-0.5 truncate text-xs text-slate-500">
                        {candidate.authors?.length ? candidate.authors.join('; ') : 'Unknown authors'}
                        {candidate.year ? `(${candidate.year})` : ''}
                      </p>
                      <p class="truncate text-xs text-slate-400">
                        {candidate.source ?? 'source'}
                        {candidate.doi ? ` · doi:${candidate.doi}` : ''}
                        {candidate.confidence != null ? ` · ${Math.round(candidate.confidence * 100)}%` : ''}
                      </p>
                    </div>
                    <button
                      onclick={() => applyCandidate(i)}
                      disabled={applyingCandidate !== null}
                      class="shrink-0 rounded-lg border border-amber-400 px-3 py-1.5 text-xs font-medium text-amber-700 hover:bg-amber-100 disabled:opacity-50"
                    >
                      {applyingCandidate === i ? 'Applying…' : 'Use this'}
                    </button>
                  </div>
                {/each}
              </div>
            </div>
          {/if}
        </div>
        <div class="flex justify-end gap-2 border-t border-slate-200 px-5 py-3">
          <button
            onclick={() => (metaModal = null)}
            class="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 hover:bg-slate-100"
          >
            Cancel
          </button>
          <button
            onclick={saveMeta}
            disabled={metaSaving}
            class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500 disabled:opacity-50"
          >
            {metaSaving ? 'Saving…' : 'Save changes'}
          </button>
        </div>
      {/if}
    </div>
  </div>
{/if}
