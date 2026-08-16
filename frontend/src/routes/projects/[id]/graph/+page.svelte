<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import KnowledgeGraph from '$lib/features/graph/components/KnowledgeGraph.svelte';
  import { installPerfWatch } from '$lib/features/graph/perf';
  import {
    addTrackedConcept,
    deleteGraphCheckpoint,
    getDocumentThemes,
    getGraphCheckpoint,
    listGraphHistory,
    listTrackedConcepts,
    refineSearchQuery,
    removeTrackedConcept,
    setCheckpointFavourite,
    startGraphGeneration,
  } from '$lib/features/graph/api';
  import type {
    DocumentThemes,
    GraphCheckpoint,
    GraphResponse,
    TrackedConcept,
  } from '$lib/features/graph/types';
  import {
    actions as actionList,
    pauseAction,
    refreshActions,
    resumeAction,
  } from '$lib/features/actions/store';

  const projectId = $derived($page.params.id);

  onMount(() => installPerfWatch());

  $effect(() => {
    if (!filterOpen) return;
    const onDown = (e: PointerEvent) => {
      if (!filterBox?.contains(e.target as Node)) filterOpen = false;
    };
    document.addEventListener('pointerdown', onDown);
    return () => document.removeEventListener('pointerdown', onDown);
  });

  let graph = $state<GraphResponse | null>(null);
  let error = $state('');
  let filter = $state('');
  let filterOpen = $state(false);
  let filterBox: HTMLDivElement | undefined;
  let tracked = $state<TrackedConcept[]>([]);
  let trackedOnly = $state(false);
  let themes = $state<DocumentThemes[]>([]);
  let trackError = $state('');
  let history = $state<GraphCheckpoint[]>([]);
  let activeCheckpointId = $state<string | null>(null);
  const generating = $derived(
    ($actionList ?? []).find(
      (a) =>
        a.kind === 'graph' &&
        a.project_id === projectId &&
        (a.status === 'queued' || a.status === 'running' || a.status === 'paused')
    ) ?? null
  );
  let handledGens = $state<string[]>([]);
  let checkpointLoading = $state(false);
  let aiMatches = $state<string[]>([]);
  let refineToken = 0;

  $effect(() => {
    const q = filter?.trim() ?? '';
    aiMatches = [];
    if (!q || !projectId) return;
    const token = ++refineToken;
    const timer = setTimeout(async () => {
      try {
        const matches = await refineSearchQuery(projectId, q);
        if (token === refineToken) aiMatches = matches ?? [];
      } catch {
        if (token === refineToken) aiMatches = [];
      }
    }, 450);
    return () => clearTimeout(timer);
  });

  async function loadThemes() {
    if (!projectId) return;
    try {
      themes = await getDocumentThemes(projectId);
    } catch {
      themes = [];
    }
  }

  async function loadHistory() {
    if (!projectId) return;
    try {
      history = await listGraphHistory(projectId);
    } catch {
      history = [];
    }
  }

  $effect(() => {
    if (!projectId) return;
    graph = null;
    tracked = [];
    trackedOnly = false;
    filter = '';
    themes = [];
    trackError = '';
    history = [];
    activeCheckpointId = null;
    handledGens = [];
    checkpointLoading = false;
    loadHistory();
    listTrackedConcepts(projectId)
      .then((concepts) => (tracked = concepts ?? []))
      .catch(() => {
        /* tracked list unavailable; graph still renders */
      });
    loadThemes();
  });

  $effect(() => {
    if (!projectId) return;
    for (const a of $actionList ?? []) {
      if (a.kind !== 'graph' || a.project_id !== projectId) continue;
      if (a.status !== 'done' && a.status !== 'error') continue;
      if (handledGens.includes(a.id)) continue;
      handledGens = [...handledGens, a.id];
      if (a.status === 'done') {
        void loadThemes();
        void loadHistory();
        if (a.checkpoint?.id) void loadCheckpoint(a.checkpoint.id);
      } else {
        error = a.error ?? 'Graph generation failed';
      }
    }
  });

  async function generate() {
    if (!projectId || generating?.status === 'running') return;
    try {
      await startGraphGeneration(projectId);
      await refreshActions();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e ?? 'Unknown error');
    }
  }

  async function toggleGenPause() {
    if (!generating) return;
    try {
      if (generating.status === 'paused') await resumeAction(generating.id);
      else await pauseAction(generating.id);
      await refreshActions();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e ?? 'Could not pause generation');
    }
  }

  async function loadCheckpoint(checkpointId: string) {
    if (!checkpointId) return;
    const project = projectId;
    checkpointLoading = true;
    error = '';
    try {
      const detail = await getGraphCheckpoint(checkpointId);
      if (project !== projectId) return;
      graph = detail?.graph ?? { nodes: [], edges: [] };
      activeCheckpointId = checkpointId;
    } catch (e) {
      if (project !== projectId) return;
      error = e instanceof Error ? e.message : String(e ?? 'Unknown error');
    } finally {
      if (project === projectId) checkpointLoading = false;
    }
  }

  async function toggleFavourite(checkpoint: GraphCheckpoint) {
    try {
      const updated = await setCheckpointFavourite(checkpoint.id, !checkpoint.is_favourite);
      history = (history ?? []).map((c) => (c.id === checkpoint.id ? updated : c));
    } catch (e) {
      error = e instanceof Error ? e.message : String(e ?? 'Unknown error');
    }
  }

  async function removeCheckpoint(checkpoint: GraphCheckpoint) {
    try {
      await deleteGraphCheckpoint(checkpoint.id);
      const wasActive = activeCheckpointId === checkpoint.id;
      history = (history ?? []).filter((c) => c.id !== checkpoint.id);
      if (wasActive) {
        graph = null;
        activeCheckpointId = null;
      }
    } catch (e) {
      error = e instanceof Error ? e.message : String(e ?? 'Unknown error');
    }
  }

  function reload() {
    generate();
  }

  function formatCheckpointTime(iso: string): string {
    if (!iso) return '—';
    const d = new Date(iso.includes('T') ? iso : `${iso.replace(' ', 'T')}Z`);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }

  async function trackAndFilter() {
    if (!filter.trim() || !projectId) return;
    filterOpen = false;
    await trackTheme(filter);
  }

  async function trackTheme(concept: string) {
    if (!projectId) return;
    if ((tracked ?? []).some((t) => String(t?.concept ?? '').toLowerCase() === concept.toLowerCase())) return;
    try {
      const added = await addTrackedConcept(projectId, concept);
      if (!added) return;
      tracked = [...(tracked ?? []), added];
    } catch (e) {
      trackError = e instanceof Error ? e.message : String(e ?? 'Unknown error');
    }
  }

  async function removeConcept(conceptId: string) {
    try {
      await removeTrackedConcept(conceptId);
      tracked = (tracked ?? []).filter((t) => t?.id !== conceptId);
      if ((tracked ?? []).length === 0) trackedOnly = false;
    } catch (e) {
      trackError = e instanceof Error ? e.message : String(e ?? 'Unknown error');
    }
  }

  const filterGroups = $derived.by(() => {
    const q = filter.trim().toLowerCase();
    const matches = (s: string) => !q || s.toLowerCase().includes(q);
    const groups: { name: string; items: string[] }[] = [];
    const concepts = (graph?.nodes ?? [])
      .filter((n) => n?.label && matches(n.label))
      .slice(0, 12);
    if (concepts.length) groups.push({ name: 'Concepts', items: concepts.map((n) => n.label) });
    const trackedOptions = (tracked ?? [])
      .map((t) => t?.concept)
      .filter((c): c is string => !!c && matches(c));
    if (trackedOptions.length) groups.push({ name: 'Tracked themes', items: trackedOptions });
    const themeOptions: string[] = [];
    for (const d of themes ?? [])
      for (const th of d?.themes ?? [])
        if (th?.concept && matches(th.concept)) themeOptions.push(th.concept);
    if (themeOptions.length) groups.push({ name: 'Detected themes', items: themeOptions });
    return groups;
  });

  function matchedCount(concept: string): number {
    const c = String(concept ?? '').toLowerCase();
    if (!c) return 0;
    let count = 0;
    for (const n of graph?.nodes ?? []) {
      const l = String(n?.label ?? '').toLowerCase();
      if (l === c || (c.length >= 3 && (l.includes(c) || c.includes(l)))) count++;
    }
    return count;
  }

  function isTracked(concept: string): boolean {
    const c = String(concept ?? '').toLowerCase();
    return (tracked ?? []).some((t) => String(t?.concept ?? '').toLowerCase() === c);
  }
</script>

<div class="flex h-full flex-col">
  <div class="shrink-0 border-b border-slate-200 bg-white px-6 py-3">
    <div class="mb-3 flex flex-wrap items-center justify-between gap-2">
      <div>
        <h1 class="text-xl font-bold text-slate-900">Knowledge Graph</h1>
        {#if graph}
          <p class="text-sm text-slate-500">
            {graph?.nodes?.length ?? 0} concepts · {graph?.edges?.length ?? 0} links
          </p>
        {/if}
      </div>
      <button
        onclick={reload}
        title="Generate a new graph checkpoint"
        class="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
      >
        ↻ Generate new graph
      </button>
    </div>

    <div class="flex flex-wrap items-end gap-x-8 gap-y-3">
      <div>
        <label class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">
          Concepts &amp; themes
        </label>
        <div class="flex items-end gap-2">
          <div class="relative w-72" bind:this={filterBox}>
          <div class="relative">
            <input
              bind:value={filter}
              type="text"
              placeholder="Type to filter and track…"
              onfocus={() => (filterOpen = true)}
              oninput={() => (filterOpen = true)}
              onkeydown={(e) => {
                if (e.key === 'Escape') filterOpen = false;
                if (e.key === 'Enter') trackAndFilter();
              }}
              class="w-full rounded-lg border border-slate-300 bg-white py-1.5 pl-3 pr-8 text-sm text-slate-800 placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
            />
            {#if filter}
              <button
                type="button"
                onclick={() => (filter = '')}
                aria-label="Clear filter"
                class="absolute right-2 top-1/2 -translate-y-1/2 rounded text-slate-400 hover:text-slate-700"
              >✕</button>
            {:else}
              <span class="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-xs text-slate-400">▾</span>
            {/if}
          </div>
          {#if filterOpen}
            <div class="absolute left-0 right-0 top-full z-20 mt-1 max-h-72 overflow-y-auto rounded-lg border border-slate-200 bg-white py-1 shadow-xl">
              {#if filterGroups.length === 0}
                <p class="px-3 py-2 text-xs text-slate-400">No matching concepts.</p>
              {:else}
                {#each filterGroups as group (group.name)}
                  <p class="px-3 pb-0.5 pt-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                    {group.name}
                  </p>
                  {#each group.items as item (item)}
                    <button
                      type="button"
                      onmousedown={(e) => e.preventDefault()}
                      onclick={() => {
                        filter = item;
                        filterOpen = false;
                        trackTheme(item);
                      }}
                      class="flex w-full items-center justify-between gap-2 px-3 py-1.5 text-left text-sm text-slate-700 hover:bg-indigo-50 hover:text-indigo-700"
                    >
                      <span class="truncate">{item}</span>
                    </button>
                  {/each}
                {/each}
              {/if}
            </div>
          {/if}
        </div>
        <button
          type="button"
          onclick={trackAndFilter}
          class="rounded-lg bg-indigo-500 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-600"
        >
          Track
        </button>
        </div>
      </div>

      <div class="min-w-0 flex-1">
        <label class="mb-1 block text-xs font-semibold uppercase tracking-wider text-slate-500">
          Tracked themes
        </label>
        {#if trackError}
          <p class="mb-1.5 text-xs text-red-600">{trackError}</p>
        {/if}
        {#if (tracked ?? []).length}
          <div class="flex flex-wrap items-center gap-1.5">
            {#each tracked ?? [] as t (t?.id ?? t?.concept)}
              <span class="flex items-center gap-1.5 rounded-full border border-amber-200 bg-amber-50 py-0.5 pl-2.5 pr-1 text-xs font-medium text-amber-800">
                <span class="max-w-40 truncate" title={t?.concept ?? ''}>{t?.concept ?? ''}</span>
                {#if matchedCount(t?.concept ?? '') === 0}
                  <span class="text-[10px] text-amber-500" title="No matching concept in the graph yet">no match</span>
                {/if}
                <button
                  onclick={() => removeConcept(t?.id ?? '')}
                  aria-label="Untrack {t?.concept ?? ''}"
                  class="rounded-full px-1 text-amber-600/70 hover:bg-white hover:text-amber-800"
                >✕</button>
              </span>
            {/each}
            <button
              onclick={() => (trackedOnly = !trackedOnly)}
              class="rounded-full border px-2.5 py-0.5 text-xs font-medium {trackedOnly
                ? 'border-amber-300 bg-amber-100 text-amber-800'
                : 'border-slate-300 bg-white text-slate-600 hover:bg-slate-100'}"
            >
              {trackedOnly ? '✓ Tracked only' : 'Tracked only'}
            </button>
          </div>
        {:else}
          <p class="text-xs text-slate-400">
            Nothing tracked yet — type a concept above and press Track.
          </p>
        {/if}
      </div>
    </div>

    <div class="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 border-t border-slate-100 pt-2.5">
      {#if (themes ?? []).length === 0}
        <p class="text-[11px] text-slate-400">
          No indexed documents yet — upload and index files to detect themes.
        </p>
      {:else}
        <span class="text-xs font-semibold uppercase tracking-wider text-slate-500">Themes:</span>
        {#each themes ?? [] as doc (doc?.doc_id)}
          <span class="flex flex-wrap items-center gap-1">
            <span class="text-xs font-medium text-slate-700" title={doc?.doc_name ?? ''}>
              {doc?.doc_name ?? 'Untitled document'}
            </span>
            {#each doc?.themes ?? [] as th (th?.concept)}
              <button
                onclick={() => trackTheme(th?.concept ?? '')}
                class="rounded-full border px-2 py-0.5 text-[11px] {isTracked(th?.concept ?? '')
                  ? 'border-amber-300 bg-amber-100 text-amber-800'
                  : 'border-slate-300 bg-white text-slate-600 hover:border-indigo-300 hover:text-indigo-600'}"
              >
                {th?.concept ?? ''} · {th?.count ?? 0}
              </button>
            {/each}
          </span>
        {/each}
      {/if}
    </div>

    <div class="mt-3 border-t border-slate-100 pt-2.5">
      <div class="flex flex-wrap items-center gap-1.5">
        <span class="text-xs font-semibold uppercase tracking-wider text-slate-500">History:</span>
        {#if (history ?? []).length === 0}
          <p class="text-[11px] text-slate-400">
            Checkpoints appear here each time a graph is generated.
          </p>
        {:else}
          {#each history ?? [] as c (c?.id)}
            <span
              role="button"
              tabindex="0"
              onclick={() => loadCheckpoint(c?.id ?? '')}
              onkeydown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.preventDefault();
                  loadCheckpoint(c?.id ?? '');
                }
              }}
              title="Open this checkpoint"
              class="flex cursor-pointer items-center gap-1.5 rounded-lg border px-1.5 py-1 text-xs {activeCheckpointId === c?.id
                ? 'border-indigo-300 bg-indigo-50 text-indigo-800'
                : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'}"
            >
              <button
                type="button"
                onclick={(e) => {
                  e.stopPropagation();
                  toggleFavourite(c);
                }}
                aria-label="Toggle favourite"
                class="text-sm {c?.is_favourite ? 'text-amber-500' : 'text-slate-300 hover:text-amber-400'}"
              >★</button>
              <span>{formatCheckpointTime(c?.created_at ?? '')}</span>
              <span class="text-slate-400">{c?.nodes ?? 0}·{c?.edges ?? 0}</span>
              <button
                type="button"
                onclick={(e) => {
                  e.stopPropagation();
                  removeCheckpoint(c);
                }}
                aria-label="Delete checkpoint"
                class="text-slate-300 hover:text-red-500"
              >✕</button>
            </span>
          {/each}
        {/if}
      </div>
    </div>
  </div>

  <div class="relative flex-1 min-h-0 p-4">
    {#if error && !graph}
      <div class="flex h-full min-h-[420px] items-center justify-center rounded-2xl border border-red-900/40 bg-red-950/30 px-4 text-sm text-red-300">
        {error}
      </div>
    {:else if !graph}
      <div class="flex h-full min-h-[420px] flex-col items-center justify-center gap-3 rounded-2xl border border-slate-800 bg-[#0b1120] px-6 text-center">
        <p class="text-base font-medium text-slate-200">No graph yet</p>
        <p class="max-w-md text-sm text-slate-400">
          Graphs are only generated when you ask for one.
          {(history ?? []).length > 0
            ? 'Select a checkpoint from History above, or generate a new one below.'
            : 'Click Generate graph to build a checkpoint of your project.'}
        </p>
        <button
          onclick={generate}
          class="rounded-lg bg-indigo-500 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-600"
        >
          Generate graph
        </button>
      </div>
    {:else}
      <KnowledgeGraph {graph} {filter} {tracked} {trackedOnly} {aiMatches} {projectId} />
      {#if checkpointLoading}
        <div class="absolute inset-4 z-10 flex items-center justify-center rounded-2xl bg-[#0b1120]/60 text-sm text-slate-300 backdrop-blur-sm">
          Loading checkpoint…
        </div>
      {/if}
      {#if error}
        <div class="absolute left-4 right-4 top-4 z-10 rounded-lg border border-red-900/40 bg-red-950/85 px-3 py-2 text-sm text-red-200">
          {error}
        </div>
      {/if}
      <div class="pointer-events-none absolute bottom-4 left-4 z-10 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg bg-slate-900/70 px-3 py-2 text-[11px] text-slate-300 backdrop-blur">
        <span class="flex items-center gap-1.5"><span class="inline-block h-2 w-2 rounded-full bg-indigo-400"></span>Node — frequency</span>
        <span class="flex items-center gap-1.5"><span class="inline-block h-px w-4 bg-slate-400"></span>Link — co-occurrence</span>
        <span class="flex items-center gap-1.5"><span class="inline-block h-2 w-2 rounded-full bg-sky-400"></span>Filter match</span>
        <span class="flex items-center gap-1.5"><span class="inline-block h-2 w-2 rounded-full bg-amber-500"></span>Selected</span>
        <span class="flex items-center gap-1.5"><span class="text-amber-500">★</span>Tracked</span>
      </div>
    {/if}
    {#if generating}
      <div class="absolute inset-4 z-20 flex flex-col items-center justify-center gap-3 rounded-2xl bg-[#0b1120]/85 text-sm text-slate-200 backdrop-blur-sm">
        <p>{generating.status === 'paused' ? 'Graph generation paused' : 'Generating graph…'}</p>
        <div class="h-2 w-64 overflow-hidden rounded-full bg-white/10">
          <div
            class="h-full rounded-full bg-indigo-400 transition-all duration-300"
            style="width: {Math.min(100, Math.max(0, generating.progress ?? 0))}%"
          ></div>
        </div>
        <p class="text-xs text-slate-400">
          {Math.round(generating.progress ?? 0)}% · {generating.stage ?? 'Working'}
        </p>
        <button
          onclick={toggleGenPause}
          class="rounded-lg border border-white/20 px-4 py-1.5 text-xs font-medium text-slate-100 hover:bg-white/10"
        >
          {generating.status === 'paused' ? '▶ Continue' : '⏸ Pause'}
        </button>
      </div>
    {/if}
  </div>
</div>
