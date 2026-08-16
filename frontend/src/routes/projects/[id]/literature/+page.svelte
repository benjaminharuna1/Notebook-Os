<script lang="ts">
  import { page } from '$app/stores';
  import PdfViewer from '$lib/features/documents/components/PdfViewer.svelte';
  import KnowledgeGraph from '$lib/features/graph/components/KnowledgeGraph.svelte';
  import { clusterColor } from '$lib/features/graph/clusterColor';
  import type { LiteratureEntry, LiteratureMapResponse } from '$lib/features/graph/types';
  import type { SearchResult } from '$lib/features/search/types';
  import {
    applyPaperCandidate,
    exportLiteratureMap,
    getLiteratureEntries,
    getLiteratureMap,
    getPaperMetadata,
    regenerateLiteratureEntry,
    searchPapers,
    startLiteratureBuild,
    updateLiteratureEntry,
    updatePaperMetadata,
  } from '$lib/features/literature/api';
  import type { LiteratureMetadata, MetadataCandidate } from '$lib/features/literature/api';
  import {
    actions as actionList,
    pauseAction,
    refreshActions,
    resumeAction,
  } from '$lib/features/actions/store';

  const projectId = $derived($page.params.id);

  let map = $state<LiteratureMapResponse>({ nodes: [], edges: [], clusters: [] });
  let entries = $state<LiteratureEntry[]>([]);
  let error = $state('');
  let loading = $state(false);
  let exporting = $state(false);
  const building = $derived(
    ($actionList ?? []).find(
      (a) =>
        a.kind === 'literature' &&
        a.project_id === projectId &&
        (a.status === 'queued' || a.status === 'running' || a.status === 'paused')
    ) ?? null
  );
  let handledBuilds = $state<string[]>([]);
  let view = $state<'map' | 'table'>('map');
  let edgeType = $state<'all' | 'citation' | 'similarity'>('all');
  let clusterFilter = $state<string | null>(null);

  let searchQ = $state('');
  let searchResults = $state<SearchResult[]>([]);
  let searching = $state(false);
  let searchOpen = $state(false);
  let searchError = $state('');
  let focusNodeId = $state('');

  let drafts = $state<Record<string, Record<string, string>>>({});
  let savingId = $state<string | null>(null);
  let regeneratingId = $state<string | null>(null);
  let savedId = $state<string | null>(null);
  let tableError = $state('');

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
    candidates: MetadataCandidate[];
  } | null>(null);
  let metaLoading = $state(false);
  let metaSaving = $state(false);
  let metaError = $state('');
  let applyingCandidate = $state<number | null>(null);

  let pdfModal = $state<{ paperId: string; title: string; fileType: string } | null>(null);
  let pdfLoading = $state(false);

  const tableColumns = [
    { key: 'citation', label: 'Citation (Author, Year)' },
    { key: 'research_objective', label: 'Research Objective / Questions' },
    { key: 'methodology', label: 'Methodology & Sample' },
    { key: 'key_findings', label: 'Key Findings' },
    { key: 'limitations', label: 'Limitations & Gaps' },
    { key: 'relevance', label: 'Relevance / Contribution' },
    { key: 'apa_reference', label: 'APA Reference' },
  ];

  $effect(() => {
    if (!projectId) return;
    handledBuilds = [];
    map = { nodes: [], edges: [], clusters: [] };
    entries = [];
    drafts = {};
    error = '';
    tableError = '';
    edgeType = 'all';
    clusterFilter = null;
    searchResults = [];
    searchOpen = false;
    focusNodeId = '';
    loadMap();
    loadEntries();
  });

  async function loadMap() {
    if (!projectId) return;
    loading = true;
    try {
      const m = await getLiteratureMap(projectId);
      map = m ?? { nodes: [], edges: [], clusters: [] };
    } catch (e) {
      error = e instanceof Error ? e.message : String(e ?? 'Unknown error');
    } finally {
      loading = false;
    }
  }

  async function loadEntries() {
    if (!projectId) return;
    try {
      const list = await getLiteratureEntries(projectId);
      entries = list;
      drafts = {};
      for (const entry of list) drafts[entry.paper_id] = entryToDraft(entry);
    } catch (e) {
      tableError = e instanceof Error ? e.message : String(e ?? 'Unknown error');
    }
  }

  function entryToDraft(entry: LiteratureEntry): Record<string, string> {
    return {
      citation: entry.citation ?? '',
      research_objective: entry.research_objective ?? '',
      methodology: entry.methodology ?? '',
      key_findings: entry.key_findings ?? '',
      limitations: entry.limitations ?? '',
      relevance: entry.relevance ?? '',
      apa_reference: entry.apa_reference ?? '',
    };
  }

  $effect(() => {
    if (!projectId) return;
    for (const a of $actionList ?? []) {
      if (a.kind !== 'literature' || a.project_id !== projectId) continue;
      if (a.status !== 'done' && a.status !== 'error') continue;
      if (handledBuilds.includes(a.id)) continue;
      handledBuilds = [...handledBuilds, a.id];
      if (a.status === 'done') {
        void loadMap();
        void loadEntries();
      } else {
        error = a.error ?? 'Literature map build failed';
      }
    }
  });

  async function build() {
    if (!projectId || building?.status === 'running') return;
    try {
      await startLiteratureBuild(projectId);
      await refreshActions();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e ?? 'Unknown error');
    }
  }

  async function toggleBuildPause() {
    if (!building) return;
    try {
      if (building.status === 'paused') await resumeAction(building.id);
      else await pauseAction(building.id);
      await refreshActions();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e ?? 'Could not pause the build');
    }
  }

  async function exportExcel() {
    if (!projectId || exporting) return;
    exporting = true;
    try {
      await exportLiteratureMap(projectId);
    } catch (e) {
      error = e instanceof Error ? e.message : String(e ?? 'Export failed');
    } finally {
      exporting = false;
    }
  }

  async function runSearch() {
    const q = searchQ.trim();
    if (!q || !projectId) return;
    searching = true;
    searchError = '';
    searchOpen = true;
    try {
      const response = await searchPapers(projectId, q);
      searchResults = response.results ?? [];
    } catch (e) {
      searchError = e instanceof Error ? e.message : String(e ?? 'Search failed');
      searchResults = [];
    } finally {
      searching = false;
    }
  }

  function pickResult(result: SearchResult) {
    focusNodeId = result.document_id;
    view = 'map';
    searchOpen = false;
  }

  function replaceEntry(updated: LiteratureEntry) {
    entries = entries.map((e) => (e.paper_id === updated.paper_id ? updated : e));
  }

  async function saveRow(paperId: string) {
    if (!projectId) return;
    const draft = drafts[paperId];
    if (!draft) return;
    savingId = paperId;
    tableError = '';
    try {
      const updated = await updateLiteratureEntry(projectId, paperId, {
        citation: draft.citation,
        research_objective: draft.research_objective,
        methodology: draft.methodology,
        key_findings: draft.key_findings,
        limitations: draft.limitations,
        relevance: draft.relevance,
        apa_reference: draft.apa_reference,
      });
      replaceEntry(updated);
      savedId = paperId;
    } catch (e) {
      tableError = e instanceof Error ? e.message : String(e ?? 'Save failed');
    } finally {
      savingId = null;
    }
  }

  async function regenerateRow(paperId: string) {
    if (!projectId) return;
    regeneratingId = paperId;
    tableError = '';
    try {
      const updated = await regenerateLiteratureEntry(projectId, paperId);
      replaceEntry(updated);
      drafts[paperId] = entryToDraft(updated);
      savedId = paperId;
    } catch (e) {
      tableError = e instanceof Error ? e.message : String(e ?? 'Regeneration failed');
    } finally {
      regeneratingId = null;
    }
  }

  async function openMetaModal(paperId: string) {
    if (!projectId || metaModal) return;
    metaModal = null;
    metaLoading = true;
    metaError = '';
    try {
      const meta = await getPaperMetadata(projectId, paperId);
      metaModal = {
        paperId,
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
        candidates: meta.candidates ?? [],
      };
      const paperId = metaModal.paperId;
      metaModal = null;
      await loadEntries();
      savedId = paperId;
      build();
    } catch (e) {
      metaError = e instanceof Error ? e.message : String(e ?? 'Could not apply metadata');
    } finally {
      applyingCandidate = null;
    }
  }

  async function openPdf(paperId: string) {
    if (!projectId || pdfModal) return;
    pdfModal = null;
    pdfLoading = true;
    try {
      const meta = await getPaperMetadata(projectId, paperId);
      pdfModal = {
        paperId,
        title: meta.title || 'Document preview',
        fileType: meta.file_type ?? 'pdf',
      };
    } catch (e) {
      metaError = e instanceof Error ? e.message : String(e ?? 'Could not load the document');
    } finally {
      pdfLoading = false;
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
      });
      const paperId = metaModal.paperId;
      metaModal = null;
      await loadEntries();
      savedId = paperId;
      build();
    } catch (e) {
      metaError = e instanceof Error ? e.message : String(e ?? 'Save failed');
    } finally {
      metaSaving = false;
    }
  }

  const visibleGraph = $derived.by(() => {
    let nodes = map.nodes ?? [];
    if (clusterFilter) nodes = nodes.filter((n) => n?.cluster === clusterFilter);
    const ids = new Set(nodes.map((n) => n.id));
    let edges = (map.edges ?? []).filter((e) => ids.has(e.source) && ids.has(e.target));
    if (edgeType === 'citation') edges = edges.filter((e) => e?.edge_type === 'citation');
    else if (edgeType === 'similarity') edges = edges.filter((e) => e?.edge_type === 'similarity');
    return { nodes, edges };
  });

  const counts = $derived.by(() => {
    let nodes = map.nodes ?? [];
    let edges = map.edges ?? [];
    if (clusterFilter) {
      const ids = new Set(nodes.filter((n) => n?.cluster === clusterFilter).map((n) => n.id));
      edges = edges.filter((e) => ids.has(e.source) && ids.has(e.target));
    }
    const citations = edges.filter((e) => e?.edge_type === 'citation').length;
    const similarities = edges.filter((e) => e?.edge_type === 'similarity').length;
    return { papers: nodes.length, citations, similarities };
  });

  function toggleCluster(clusterId: string) {
    clusterFilter = clusterFilter === clusterId ? null : clusterId;
  }
</script>

<div class="flex h-full flex-col">
  <div class="shrink-0 border-b border-slate-200 bg-white px-6 py-3">
    <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
      <div>
        <h1 class="text-xl font-bold text-slate-900">Literature Map</h1>
        {#if (map.nodes ?? []).length}
          <p class="text-sm text-slate-500">
            {counts.papers} papers · {counts.citations} citations · {counts.similarities} similarities
          </p>
        {/if}
      </div>
      <div class="flex items-center gap-2">
        <button
          onclick={exportExcel}
          disabled={exporting || (map.nodes ?? []).length === 0}
          class="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {exporting ? 'Exporting…' : '⇩ Export Excel'}
        </button>
        <button
          onclick={build}
          disabled={building?.status === 'running'}
          class="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
        >
          ↻ Build literature map
        </button>
      </div>
    </div>

    <div class="flex flex-wrap items-center gap-x-8 gap-y-3">
      <div class="flex items-end gap-3">
        <div>
          <label class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">
            View
          </label>
          <div class="flex overflow-hidden rounded-lg border border-slate-300 text-sm">
            {#each [
              { value: 'map', label: 'Map' },
              { value: 'table', label: 'Table' },
            ] as opt (opt.value)}
              <button
                onclick={() => (view = opt.value as 'map' | 'table')}
                class="px-3 py-1.5 {view === opt.value
                  ? 'bg-indigo-500 font-medium text-white'
                  : 'bg-white text-slate-600 hover:bg-slate-100'}"
              >
                {opt.label}
              </button>
            {/each}
          </div>
        </div>
        {#if view === 'map'}
          <div>
            <label class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">
              Edges
            </label>
            <div class="flex overflow-hidden rounded-lg border border-slate-300 text-sm">
              {#each [
                { value: 'all', label: 'All' },
                { value: 'citation', label: 'Citations' },
                { value: 'similarity', label: 'Similarity' },
              ] as opt (opt.value)}
                <button
                  onclick={() => (edgeType = opt.value as 'all' | 'citation' | 'similarity')}
                  class="px-3 py-1.5 {edgeType === opt.value
                    ? 'bg-indigo-500 font-medium text-white'
                    : 'bg-white text-slate-600 hover:bg-slate-100'}"
                >
                  {opt.label}
                </button>
              {/each}
            </div>
          </div>
        {/if}
      </div>

      {#if view === 'map'}
        <div class="relative min-w-64 flex-1 max-w-md">
          <label class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">
            Search all papers
          </label>
          <div class="flex gap-2">
            <input
              bind:value={searchQ}
              placeholder="Keywords or a statement across all papers…"
              onkeydown={(e) => {
                if (e.key === 'Enter') runSearch();
              }}
              class="flex-1 rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-indigo-500"
            />
            <button
              onclick={runSearch}
              disabled={searching}
              class="rounded-lg bg-indigo-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {searching ? '…' : 'Search'}
            </button>
          </div>
          {#if searchOpen && !searching}
            <div class="absolute left-0 right-0 top-full z-30 mt-1 max-h-72 overflow-auto rounded-lg border border-slate-200 bg-white shadow-xl">
              {#if searchError}
                <p class="p-3 text-xs text-red-600">{searchError}</p>
              {:else if searchResults.length === 0}
                <p class="p-3 text-xs text-slate-400">No matches.</p>
              {:else}
                <ul class="divide-y divide-slate-100">
                  {#each searchResults as result (result.chunk_id)}
                    <li>
                      <button
                        onclick={() => pickResult(result)}
                        class="block w-full px-3 py-2 text-left hover:bg-slate-50"
                      >
                        <p class="truncate text-xs font-medium text-slate-800">
                          {result.document_title}
                        </p>
                        <p class="mt-0.5 line-clamp-2 text-[11px] leading-snug text-slate-500">
                          {result.content}
                        </p>
                        <p class="mt-0.5 text-[10px] text-slate-400">
                          <span class="inline-flex items-center gap-1">
                            <span
                              class="rounded px-1 py-px font-medium {result.source === 'keyword'
                                ? 'bg-amber-100 text-amber-700'
                                : 'bg-sky-100 text-sky-700'}"
                            >
                              {result.source === 'keyword' ? 'keyword' : 'semantic'}
                            </span>
                            score {result.score.toFixed(2)}
                            {#if result.page_number}
                              · page {result.page_number}
                            {/if}
                          </span>
                        </p>
                      </button>
                    </li>
                  {/each}
                </ul>
              {/if}
            </div>
          {/if}
        </div>

        <div>
          <label class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">
            {clusterFilter ? 'Cluster filter' : 'Clusters'}
          </label>
          {#if (map.clusters ?? []).length === 0}
            <p class="text-xs text-slate-400">Build the map to detect clusters.</p>
          {:else}
            <div class="flex flex-wrap items-center gap-1.5">
              {#each map.clusters as c (c?.id)}
                <button
                  onclick={() => toggleCluster(c?.id ?? '')}
                  title={c?.summary || c?.label}
                  class="flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium {clusterFilter === c?.id
                    ? 'border-indigo-300 bg-indigo-50 text-indigo-800'
                    : 'border-slate-300 bg-white text-slate-600 hover:bg-slate-100'}"
                >
                  <span class="inline-block h-2.5 w-2.5 rounded-full" style="background: {clusterColor(c?.id)}"></span>
                  <span class="max-w-44 truncate">{c?.label}</span>
                  <span class="text-[10px] text-slate-400">{c?.size}</span>
                </button>
              {/each}
            </div>
          {/if}
        </div>
      {/if}
    </div>

    {#if error}
      <div class="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
        {error}
      </div>
    {/if}
    {#if tableError && view === 'table'}
      <div class="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
        {tableError}
      </div>
    {/if}
  </div>

  <div class="relative flex-1 min-h-0">
    {#if view === 'map'}
      <div class="h-full p-4">
        {#if loading}
          <div class="flex h-full min-h-[420px] items-center justify-center rounded-2xl border border-slate-800 bg-[#0b1120] px-4 text-sm text-slate-400">
            Loading literature map…
          </div>
        {:else if (map.nodes ?? []).length === 0}
          <div class="flex h-full min-h-[420px] flex-col items-center justify-center gap-3 rounded-2xl border border-slate-800 bg-[#0b1120] px-6 text-center">
            <p class="text-base font-medium text-slate-200">No literature map yet</p>
            <p class="max-w-md text-sm text-slate-400">
              Your indexed documents become papers here, connected by citations and topical
              similarity, grouped into LLM-labelled themes, and summarised into an editable
              literature matrix. The map rebuilds automatically as papers are added.
            </p>
            <button
              onclick={build}
              disabled={building?.status === 'running'}
              class="rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-600 disabled:opacity-50"
            >
              Build literature map
            </button>
          </div>
        {:else}
          <KnowledgeGraph
            graph={visibleGraph}
            projectId={projectId}
            papersMode={true}
            clusters={map.clusters ?? []}
            focusNodeId={focusNodeId}
            onEditMeta={(nodeId) => openMetaModal(nodeId)}
            onOpenPdf={(nodeId) => openPdf(nodeId)}
          />
          <div class="pointer-events-none absolute bottom-8 left-8 z-10 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg bg-slate-900/70 px-3 py-2 text-[11px] text-slate-300 backdrop-blur">
            <span class="flex items-center gap-1.5"><span class="inline-block h-2 w-2 rounded-full bg-sky-400"></span>Node — paper (theme colour)</span>
            <span class="flex items-center gap-1.5"><span class="inline-block h-px w-4 bg-amber-400"></span>Citation link</span>
            <span class="flex items-center gap-1.5"><span class="inline-block h-0 w-4 border-t border-dashed border-sky-400"></span>Similarity link</span>
          </div>
        {/if}
      </div>
    {:else}
      <div class="h-full overflow-auto p-4">
        {#if (map.nodes ?? []).length === 0}
          <div class="flex h-full min-h-[420px] flex-col items-center justify-center gap-3 rounded-2xl border border-slate-200 bg-white px-6 text-center">
            <p class="text-base font-medium text-slate-700">No literature matrix yet</p>
            <p class="max-w-md text-sm text-slate-400">
              Build the literature map first — each paper gets an auto-generated row you can
              edit, and the whole matrix exports to Excel.
            </p>
            <button
              onclick={build}
              disabled={building?.status === 'running'}
              class="rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-600 disabled:opacity-50"
            >
              Build literature map
            </button>
          </div>
        {:else if entries.length === 0}
          <div class="flex h-full min-h-[420px] flex-col items-center justify-center gap-3 rounded-2xl border border-slate-200 bg-white px-6 text-center">
            <p class="text-base font-medium text-slate-700">Entries not generated yet</p>
            <p class="max-w-md text-sm text-slate-400">
              Rebuild the map to generate and auto-summarise a row for every paper.
            </p>
            <button
              onclick={build}
              disabled={building?.status === 'running'}
              class="rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-600 disabled:opacity-50"
            >
              Build literature map
            </button>
          </div>
        {:else}
          <table class="min-w-[1500px] border-collapse text-left">
            <thead class="sticky top-0 z-10 bg-slate-100">
              <tr>
                <th class="border-b border-slate-200 p-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Paper
                </th>
                {#each tableColumns as col (col.key)}
                  <th class="border-b border-slate-200 p-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                    {col.label}
                  </th>
                {/each}
                <th class="w-36 border-b border-slate-200 p-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody>
              {#each entries as entry (entry.paper_id)}
                {@const draft = drafts[entry.paper_id] ?? (drafts[entry.paper_id] = entryToDraft(entry))}
                <tr class="align-top bg-white">
                  <td class="border-b border-slate-100 p-2">
                    <p class="max-w-48 text-xs font-medium leading-snug text-slate-800">
                      {entry.title}
                    </p>
                    <p class="mt-1 text-[10px] text-slate-400">
                      {entry.auto_generated ? 'Auto-generated' : 'Edited'}
                    </p>
                  </td>
                  {#each tableColumns as col (col.key)}
                    <td class="border-b border-slate-100 p-2">
                      <textarea
                        bind:value={draft[col.key]}
                        placeholder="—"
                        class="h-28 w-full resize-y rounded border border-slate-200 bg-white p-2 text-xs leading-relaxed text-slate-700 outline-none focus:border-indigo-400"
                      ></textarea>
                    </td>
                  {/each}
                  <td class="border-b border-slate-100 p-2">
                    <button
                      onclick={() => openPdf(entry.paper_id)}
                      class="w-full rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100"
                    >
                      Open PDF
                    </button>
                    <button
                      onclick={() => openMetaModal(entry.paper_id)}
                      class="mt-1.5 w-full rounded-md border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100"
                    >
                      Edit metadata
                    </button>
                    <button
                      onclick={() => saveRow(entry.paper_id)}
                      disabled={savingId === entry.paper_id}
                      class="mt-1.5 w-full rounded-md border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-100 disabled:opacity-50"
                    >
                      {savingId === entry.paper_id ? 'Saving…' : 'Save'}
                    </button>
                    <button
                      onclick={() => regenerateRow(entry.paper_id)}
                      disabled={regeneratingId === entry.paper_id}
                      class="mt-1.5 w-full rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-100 disabled:opacity-50"
                    >
                      {regeneratingId === entry.paper_id ? 'Generating…' : 'Regenerate with AI'}
                    </button>
                    {#if savedId === entry.paper_id}
                      <p class="mt-1 text-center text-[10px] text-emerald-600">Saved</p>
                    {/if}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </div>
    {/if}

    {#if building}
      <div class="absolute inset-4 z-40 flex flex-col items-center justify-center gap-3 rounded-2xl bg-[#0b1120]/85 text-sm text-slate-200 backdrop-blur-sm">
        <p>{building.status === 'paused' ? 'Literature map build paused' : 'Building literature map…'}</p>
        <div class="h-2 w-64 overflow-hidden rounded-full bg-white/10">
          <div
            class="h-full rounded-full bg-indigo-400 transition-all duration-300"
            style="width: {Math.min(100, Math.max(0, building.progress ?? 0))}%"
          ></div>
        </div>
        <p class="text-xs text-slate-400">
          {Math.round(building.progress ?? 0)}% · {building.stage ?? 'Working'}
        </p>
        <button
          onclick={toggleBuildPause}
          class="rounded-lg border border-white/20 px-4 py-1.5 text-xs font-medium text-slate-100 hover:bg-white/10"
        >
          {building.status === 'paused' ? '▶ Continue' : '⏸ Pause'}
        </button>
      </div>
    {/if}
  </div>

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
            </div>
            <div>
              <label class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">
                Journal
              </label>
              <input
                bind:value={metaModal.journal}
                placeholder="Journal of Example Research"
                class="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-indigo-500"
              />
            </div>
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

  {#if pdfModal}
    <div class="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/50 p-4 backdrop-blur-sm">
      <div class="flex h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl bg-white shadow-2xl">
        <div class="flex items-center justify-between gap-3 border-b border-slate-200 px-5 py-3">
          <h2 class="truncate text-base font-semibold text-slate-900">{pdfModal.title}</h2>
          <button
            onclick={() => (pdfModal = null)}
            class="shrink-0 text-slate-400 hover:text-slate-700"
            aria-label="Close"
          >✕</button>
        </div>
        <div class="min-h-0 flex-1">
          <PdfViewer
            projectId={projectId}
            documentId={pdfModal.paperId}
            title={pdfModal.title}
            fileType={pdfModal.fileType}
          />
        </div>
      </div>
    </div>
  {/if}
</div>
