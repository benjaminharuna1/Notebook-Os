<script lang="ts">
  import { untrack } from 'svelte';
  import { streamConceptSummary } from '$lib/features/graph/api';
  import { clusterColor } from '$lib/features/graph/clusterColor';
  import type {
    ConceptSource,
    ClusterInfo,
    GraphResponse,
    TrackedConcept,
  } from '$lib/features/graph/types';

  let {
    graph,
    filter = '',
    tracked = [],
    trackedOnly = false,
    aiMatches = [],
    projectId = '',
    papersMode = false,
    clusters = [],
    focusNodeId = '',
    onEditMeta = null,
    onOpenPdf = null,
  }: {
    graph: GraphResponse | null;
    filter?: string | null;
    tracked?: TrackedConcept[] | null;
    trackedOnly?: boolean | null;
    aiMatches?: string[] | null;
    projectId?: string | null;
    papersMode?: boolean | null;
    clusters?: ClusterInfo[] | null;
    focusNodeId?: string | null;
    onEditMeta?: ((nodeId: string) => void) | null;
    onOpenPdf?: ((nodeId: string) => void) | null;
  } = $props();

  const safeFilter = $derived(String(filter ?? ''));
  const safeTracked = $derived((tracked ?? []) as TrackedConcept[]);
  const safeTrackedOnly = $derived(Boolean(trackedOnly));
  const papersModeOn = $derived(Boolean(papersMode));

  interface SimNode {
    id: string;
    label: string;
    weight: number;
    x: number;
    y: number;
    enter: boolean;
    cluster?: string | null;
    meta?: Record<string, any> | null;
  }

  interface SimEdge {
    source: string;
    target: string;
    weight: number;
    edge_type?: string | null;
  }

  let layoutNodes = $state<SimNode[]>([]);
  let layoutEdges = $state<SimEdge[]>([]);
  let maxNodeWeight = $state(1);
  let maxEdgeWeight = $state(1);

  let highlighted = $state<string | null>(null);
  let selected = $state<string | null>(null);
  let dragging = $state<string | null>(null);
  let cam = $state({ x: 0, y: 0, k: 1 });
  let panning = $state(false);
  let panStart = $state({ x: 0, y: 0, cx: 0, cy: 0 });
  let tooltipEl = $state<HTMLDivElement | null>(null);
  let container = $state<HTMLDivElement | null>(null);
  let reveal = $state(false);

  interface ConceptSummary {
    status: 'idle' | 'loading' | 'streaming' | 'done' | 'error';
    text: string;
    sources: ConceptSource[];
    error?: string;
  }

  let summary = $state<ConceptSummary>({ status: 'idle', text: '', sources: [] });
  let summaryToken = 0;

  $effect(() => {
    const sel = selected;
    summary = { status: 'idle', text: '', sources: [] };
    if (!sel || !projectId) return;
    if (papersModeOn) return;
    const label = untrack(() => layoutNodes.find((n) => n.id === sel)?.label ?? '');
    if (!label) return;
    const token = ++summaryToken;
    summary.status = 'loading';
    const stop = streamConceptSummary(
      projectId,
      label,
      (chunk) => {
        if (token !== summaryToken) return;
        summary.status = 'streaming';
        summary.text += chunk;
      },
      (sources) => {
        if (token !== summaryToken) return;
        summary.sources = sources ?? [];
      },
      () => {
        if (token !== summaryToken) return;
        if (summary.status !== 'error') summary.status = 'done';
      },
      (e) => {
        if (token !== summaryToken) return;
        summary.status = 'error';
        summary.error = e.message;
      },
    );
    return () => {
      summaryToken++;
      stop();
    };
  });

  const W = 800;
  const H = 600;
  let firstLayout = true;

  $effect(() => {
    const id = focusNodeId;
    if (!id) return;
    if (layoutNodes.some((n) => n.id === id)) {
      selected = id;
      highlighted = id;
    }
  });

  $effect(() => {
    const g = graph;
    if (!g) {
      firstLayout = true;
      return;
    }
    untrack(() => {
      selected = null;
      highlighted = null;
      applyGraph(g);
    });
  });

  function applyGraph(g: GraphResponse) {
    const t0 = window.__GRAPH_PERF__ ? performance.now() : 0;
    const prevById = new Map(layoutNodes.map((n) => [n.id, n]));
    const next: SimNode[] = [];

    for (const n of g.nodes ?? []) {
      const id = String(n?.id ?? '');
      if (!id) continue;
      const label = String(n?.label ?? '');
      const weight = Number(n?.weight) || 0;
      const x = Number(n?.x);
      const y = Number(n?.y);
      const cluster = n?.cluster ? String(n.cluster) : null;
      const meta = n?.meta && typeof n.meta === 'object' ? (n.meta as Record<string, any>) : null;
      const hasPos = Number.isFinite(x) && Number.isFinite(y) && (x !== 0 || y !== 0);
      const existing = prevById.get(id);
      if (existing) {
        existing.label = label;
        existing.weight = weight;
        existing.cluster = cluster ?? existing.cluster;
        existing.meta = meta ?? existing.meta;
        if (hasPos) {
          existing.x = x;
          existing.y = y;
        }
        next.push(existing);
      } else {
        next.push({
          id,
          label,
          weight,
          x: hasPos ? x : W / 2 + (Math.random() - 0.5) * 140,
          y: hasPos ? y : H / 2 + (Math.random() - 0.5) * 140,
          enter: false,
          cluster,
          meta,
        });
      }
    }

    layoutNodes = next;
    layoutEdges = (g.edges ?? [])
      .filter((e) => e && e.source && e.target)
      .map((e) => ({
        source: e.source,
        target: e.target,
        weight: Number(e.weight) || 0,
        edge_type: e?.edge_type ? String(e.edge_type) : null,
      }));
    maxNodeWeight = Math.max(1, ...layoutNodes.map((n) => n.weight));
    maxEdgeWeight = Math.max(1, ...layoutEdges.map((e) => e.weight));

    if (firstLayout) {
      fitView();
      firstLayout = false;
      setTimeout(() => {
        layoutNodes.forEach((n, i) => setTimeout(() => (n.enter = true), (i % 16) * 12));
        reveal = true;
      }, 60);
    } else {
      layoutNodes.forEach((n) => {
        if (!n.enter) setTimeout(() => (n.enter = true), 30);
      });
    }
    if (window.__GRAPH_PERF__) {
      const ms = performance.now() - t0;
      if (ms >= 30) console.warn(`[perf] applyGraph took ${Math.round(ms)}ms`);
    }
  }

  function scatter() {
    for (const n of layoutNodes) {
      n.x = W / 2 + (Math.random() - 0.5) * W * 0.6;
      n.y = H / 2 + (Math.random() - 0.5) * H * 0.6;
      n.enter = false;
    }
  }

  function rearrange() {
    scatter();
    fitView();
    selected = null;
    layoutNodes.forEach((n, i) => setTimeout(() => (n.enter = true), (i % 16) * 8));
  }

  const degreeOf = $derived.by(() => {
    const d = new Map<string, number>();
    for (const e of layoutEdges) {
      d.set(e.source, (d.get(e.source) ?? 0) + 1);
      d.set(e.target, (d.get(e.target) ?? 0) + 1);
    }
    return d;
  });

  const adjacency = $derived.by(() => {
    const m = new Map<string, Set<string>>();
    for (const e of layoutEdges) {
      let s = m.get(e.source);
      if (!s) m.set(e.source, (s = new Set()));
      s.add(e.target);
      let t = m.get(e.target);
      if (!t) m.set(e.target, (t = new Set()));
      t.add(e.source);
    }
    return m;
  });

  const nodePos = $derived.by(() => {
    const m = new Map<string, { x: number; y: number }>();
    for (const n of layoutNodes) m.set(n.id, n);
    return m;
  });

  const matchQuery = $derived.by(() => {
    const q = safeFilter.trim().toLowerCase();
    const ai = new Set((aiMatches ?? []).map((m) => String(m ?? '').toLowerCase()));
    if (!q && ai.size === 0) return null;
    const set = new Set<string>();
    for (const n of layoutNodes) {
      const label = n.label.toLowerCase();
      if (label.includes(q)) set.add(n.id);
      if (ai.has(label)) set.add(n.id);
    }
    return set;
  });

  const selectedNode = $derived.by(() => layoutNodes.find((n) => n.id === selected) ?? null);

  const selectedNeighbors = $derived.by(() => {
    if (!selectedNode) return [];
    return neighbors(selectedNode.id)
      .map((n) => ({ node: n, weight: edgeWeight(selectedNode.id, n.id) }))
      .sort((a, b) => b.weight - a.weight)
      .slice(0, 6);
  });

  const activeSet = $derived.by(() => {
    if (matchQuery) return matchQuery;
    if (safeTrackedOnly) return trackedMatchIds;
    if (selected !== null) return new Set([selected]);
    if (highlighted !== null) return new Set([highlighted]);
    return null;
  });

  const trackedSet = $derived.by(() => new Set(safeTracked.map((t) => (t?.concept ?? '').toLowerCase())));

  const trackedMatchIds = $derived.by(() => {
    const ids = new Set<string>();
    for (const n of layoutNodes) {
      if (matchesTracked(n.label)) ids.add(n.id);
    }
    return ids;
  });

  const filterModeIds = $derived.by(() => {
    if (matchQuery) return matchQuery;
    if (safeTrackedOnly) return trackedMatchIds;
    return null;
  });

  const displayNodes = $derived.by(() => {
    if (!filterModeIds) return layoutNodes;
    return layoutNodes.filter((n) => filterModeIds.has(n.id));
  });

  const displayEdges = $derived.by(() => {
    if (!filterModeIds) return layoutEdges;
    return layoutEdges.filter((e) => filterModeIds.has(e.source) && filterModeIds.has(e.target));
  });

  function matchesTracked(label: string): boolean {
    const l = String(label ?? '').toLowerCase();
    for (const c of trackedSet) {
      if (l === c) return true;
      if (c.length >= 3 && (l.includes(c) || c.includes(l))) return true;
    }
    return false;
  }

  function neighbors(id: string): SimNode[] {
    const set = new Set<string>();
    for (const e of layoutEdges) {
      if (e.source === id) set.add(e.target);
      if (e.target === id) set.add(e.source);
    }
    const byId = new Map(layoutNodes.map((n) => [n.id, n]));
    return [...set]
      .map((i) => byId.get(i))
      .filter((n): n is SimNode => Boolean(n));
  }

  function connectedTo(a: string, b: string) {
    return adjacency.get(a)?.has(b) ?? false;
  }

  function edgeWeight(a: string, b: string) {
    const e = layoutEdges.find(
      (x) => (x.source === a && x.target === b) || (x.source === b && x.target === a),
    );
    return e?.weight ?? 0;
  }

  function nodeById(id: string) {
    return layoutNodes.find((n) => n.id === id) ?? null;
  }

  function nodeRadius(n: SimNode) {
    return 9 + (n.weight / maxNodeWeight) * 13;
  }

  function nodeDim(n: SimNode): number {
    if (dragging === n.id) return 1;
    if (activeSet) {
      if (activeSet.has(n.id)) return 1;
      for (const id of activeSet) {
        if (connectedTo(id, n.id)) return 0.85;
      }
      return 0.12;
    }
    return 1;
  }

  function edgeDim(e: SimEdge): number {
    if (!activeSet) return 0.42 + (e.weight / maxEdgeWeight) * 0.4;
    const s = activeSet.has(e.source);
    const t = activeSet.has(e.target);
    if (s && t) return 0.9;
    if (s || t) return 0.6;
    return 0.25;
  }

  const clusterName = $derived.by(() => {
    const m = new Map<string, string>();
    for (const c of clusters ?? []) m.set(c?.id ?? '', c?.label ?? '');
    return m;
  });

  function clusterLabel(id: string | null | undefined): string {
    if (!id) return '';
    return clusterName.get(id) ?? `Cluster ${id.replace(/^c/, '')}`;
  }

  function nodeFill(n: SimNode): string {
    if (selected === n.id) return '#fbbf24';
    if (papersModeOn && n.cluster) return clusterColor(n.cluster);
    if (matchQuery?.has(n.id)) return '#38bdf8';
    if (safeTrackedOnly && trackedMatchIds.has(n.id)) return '#f59e0b';
    return n.weight >= maxNodeWeight * 0.5 ? '#a5b4fc' : '#818cf8';
  }

  function edgeStroke(e: SimEdge): string {
    if (e.edge_type === 'citation') return '#f59e0b';
    if (e.edge_type === 'similarity') return '#38bdf8';
    return '#94a3b8';
  }

  function edgeDash(e: SimEdge): string | null {
    if (e.edge_type === 'similarity') return '4 3';
    return null;
  }

  function labelFill(n: SimNode): string {
    if (selected === n.id || matchQuery?.has(n.id) || trackedMatchIds.has(n.id)) return '#f1f5f9';
    return '#94a3b8';
  }

  function truncate(label: string) {
    const l = String(label ?? '');
    return l.length > 20 ? `${l.slice(0, 19)}…` : l;
  }

  // --- camera -------------------------------------------------------------

  function zoomBy(factor: number, cx?: number, cy?: number) {
    const px = cx ?? W / 2;
    const py = cy ?? H / 2;
    const k2 = Math.min(3, Math.max(0.4, cam.k * factor));
    const kf = k2 / cam.k;
    cam = { x: px - (px - cam.x) * kf, y: py - (py - cam.y) * kf, k: k2 };
  }

  function fitView() {
    if (!layoutNodes.length) {
      cam = { x: 0, y: 0, k: 1 };
      return;
    }
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const n of layoutNodes) {
      const r = nodeRadius(n) + 16;
      minX = Math.min(minX, n.x - r);
      maxX = Math.max(maxX, n.x + r);
      minY = Math.min(minY, n.y - r);
      maxY = Math.max(maxY, n.y + r);
    }
    const k = Math.min(
      (W - 70) / Math.max(1, maxX - minX),
      (H - 70) / Math.max(1, maxY - minY),
      1.6,
    );
    cam = {
      x: W / 2 - ((minX + maxX) / 2) * k,
      y: H / 2 - ((minY + maxY) / 2) * k,
      k,
    };
  }

  function onWheel(e: WheelEvent) {
    e.preventDefault();
    const rect = container?.getBoundingClientRect();
    if (!rect) return;
    const px = ((e.clientX - rect.left) / rect.width) * W;
    const py = ((e.clientY - rect.top) / rect.height) * H;
    zoomBy(e.deltaY < 0 ? 1.12 : 1 / 1.12, px, py);
  }

  $effect(() => {
    if (!container) return;
    container.addEventListener('wheel', onWheel, { passive: false });
    return () => container.removeEventListener('wheel', onWheel);
  });

  function canvasPoint(e: PointerEvent) {
    const rect = container?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return {
      x: ((e.clientX - rect.left) / rect.width) * W,
      y: ((e.clientY - rect.top) / rect.height) * H,
    };
  }

  function onCanvasDown(e: PointerEvent) {
    const target = e.target as Element | null;
    if (target?.closest('g.node')) return;
    if (e.button === 0) {
      panning = true;
      panStart = { x: e.clientX, y: e.clientY, cx: cam.x, cy: cam.y };
      selected = null;
      highlighted = null;
      (e.currentTarget as Element).setPointerCapture(e.pointerId);
    }
  }

  function positionTooltip(e: { clientX: number; clientY: number }) {
    if (!highlighted || dragging || !nodeById(highlighted)) return;
    const el = tooltipEl;
    const rect = container?.getBoundingClientRect();
    if (!el || !rect) return;
    const x = ((e.clientX - rect.left) / rect.width) * W;
    const y = ((e.clientY - rect.top) / rect.height) * H;
    el.style.transform = `translate(${x}px, ${y + 8}px) translate(-50%, -100%)`;
  }

  function onCanvasMove(e: PointerEvent) {
    if (panning) {
      cam = {
        ...cam,
        x: panStart.cx + (e.clientX - panStart.x),
        y: panStart.cy + (e.clientY - panStart.y),
      };
      return;
    }
    positionTooltip(e);
  }

  function onCanvasUp() {
    panning = false;
  }

  function onNodeDown(e: PointerEvent, n: SimNode) {
    e.stopPropagation();
    dragging = n.id;
    selected = n.id;
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
  }

  function onNodeMove(e: PointerEvent, n: SimNode) {
    if (dragging !== n.id) return;
    const pt = canvasPoint(e);
    n.x = (pt.x - cam.x) / cam.k;
    n.y = (pt.y - cam.y) / cam.k;
  }

  function onNodeUp() {
    dragging = null;
  }

  function onNodeKeydown(e: KeyboardEvent, n: SimNode) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      selected = n.id;
    }
  }

  $effect(() => {
    const up = () => {
      dragging = null;
      panning = false;
    };
    window.addEventListener('pointerup', up);
    return () => window.removeEventListener('pointerup', up);
  });
</script>

{#if !graph || (graph.nodes?.length ?? 0) === 0}
  <div class="flex h-full min-h-[420px] items-center justify-center rounded-2xl border border-slate-800 bg-[#0b1120] px-4 text-center text-slate-400">
    {papersModeOn
      ? 'No literature map yet — build one from your indexed documents.'
      : 'No knowledge graph yet — upload and index documents in this project.'}
  </div>
{:else}
  <div
    bind:this={container}
    class="relative h-full min-h-[420px] w-full overflow-hidden rounded-2xl border border-slate-800 bg-[#0b1120] select-none"
    role="img"
    aria-label="Interactive knowledge graph"
  >
    <svg
      viewBox="0 0 {W} {H}"
      class="h-full w-full"
      role="group"
      aria-label="Knowledge graph canvas"
      onpointerdown={onCanvasDown}
      onpointermove={onCanvasMove}
      onpointerup={onCanvasUp}
    >
      <defs>
        <pattern id="kg-dots" width="26" height="26" patternUnits="userSpaceOnUse">
          <circle cx="2" cy="2" r="1.1" fill="#ffffff" opacity="0.07" />
        </pattern>
      </defs>

      <rect width={W} height={H} fill="url(#kg-dots)" />

      <g transform="translate({cam.x} {cam.y}) scale({cam.k})" opacity={reveal ? 1 : 0}
        style="transition: opacity 0.45s ease">
        {#each displayEdges as e (e.source + e.target)}
          <line
            x1={nodePos.get(e.source)?.x ?? 0}
            y1={nodePos.get(e.source)?.y ?? 0}
            x2={nodePos.get(e.target)?.x ?? 0}
            y2={nodePos.get(e.target)?.y ?? 0}
            stroke={edgeStroke(e)}
            stroke-linecap="round"
            stroke-width={0.5 + (e.weight / maxEdgeWeight) * 2.5}
            stroke-opacity={edgeDim(e)}
            stroke-dasharray={edgeDash(e)}
          />
        {/each}

        {#each displayNodes as n, i (n.id)}
          {@const r = nodeRadius(n)}
          {@const dim = nodeDim(n)}
          <g
            class="node {dragging === n.id ? 'dragging' : ''}"
            style="translate: {n.x}px {n.y}px; scale: {n.enter ? 'var(--s, 1)' : '0.05'}; opacity: {dim};"
            role="button"
            tabindex="0"
            aria-label="{n.label}, {n.weight} chunks"
            onpointerdown={(e) => onNodeDown(e, n)}
            onpointermove={(e) => onNodeMove(e, n)}
            onpointerup={onNodeUp}
            onpointerleave={() => {
              if (dragging === n.id) dragging = null;
            }}
            onmouseenter={(e) => {
              highlighted = n.id;
              positionTooltip(e);
            }}
            onmouseleave={() => (highlighted = null)}
            onclick={(e) => {
              e.stopPropagation();
              selected = n.id;
            }}
            onkeydown={(e) => onNodeKeydown(e, n)}
          >
            <circle cx="0" cy="0" r={r * 1.8} fill={nodeFill(n)} opacity="0.16" aria-hidden="true" />
            <circle
              cx="0"
              cy="0"
              r={r}
              fill={nodeFill(n)}
              stroke={trackedMatchIds.has(n.id) ? '#fbbf24' : '#0b1120'}
              stroke-width={trackedMatchIds.has(n.id) ? 2 : 1.5}
            />
            {#if trackedMatchIds.has(n.id)}
              <text
                x={r * 0.85}
                y={-r * 0.7}
                text-anchor="middle"
                font-size="11"
                fill="#fbbf24"
                pointer-events="none"
                aria-hidden="true"
              >★</text>
            {/if}
            <text
              x="0"
              y={r + 13}
              text-anchor="middle"
              font-size="11"
              font-weight={n.weight >= maxNodeWeight * 0.5 ? '600' : '400'}
              fill={labelFill(n)}
              pointer-events="none"
            >
              {truncate(n.label)}
            </text>
          </g>
        {/each}
      </g>
    </svg>

    <div class="pointer-events-none absolute inset-0" style="background: radial-gradient(ellipse at center, transparent 55%, rgba(2,6,23,0.55) 100%)" aria-hidden="true"></div>

    <div class="absolute right-3 top-3 z-10 flex flex-col gap-1.5">
      <button
        onclick={() => zoomBy(1.25)}
        aria-label="Zoom in"
        class="flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-slate-900/70 text-base text-slate-200 backdrop-blur hover:bg-slate-700/60 hover:text-white"
      >+</button>
      <button
        onclick={() => zoomBy(0.8)}
        aria-label="Zoom out"
        class="flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-slate-900/70 text-base text-slate-200 backdrop-blur hover:bg-slate-700/60 hover:text-white"
      >−</button>
      <button
        onclick={fitView}
        aria-label="Fit graph to view"
        class="flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-slate-900/70 text-sm text-slate-200 backdrop-blur hover:bg-slate-700/60 hover:text-white"
      >⤢</button>
      <button
        onclick={rearrange}
        aria-label="Rearrange layout"
        class="flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-slate-900/70 text-sm text-slate-200 backdrop-blur hover:bg-slate-700/60 hover:text-white"
      >⟳</button>
    </div>

    <div
      bind:this={tooltipEl}
      class="pointer-events-none absolute left-0 top-0 z-10 rounded-lg border border-white/10 bg-slate-900/90 px-3 py-2 text-xs text-slate-100 shadow-xl backdrop-blur"
      style="opacity: {highlighted && !dragging && nodeById(highlighted) ? 1 : 0}; transition: opacity 0.12s ease;"
      aria-hidden="true"
    >
      {#if nodeById(highlighted)}
        {@const hn = nodeById(highlighted)!}
        <p class="font-medium">{hn.label}</p>
        {#if papersModeOn}
          <p class="mt-0.5 text-slate-400">
            {hn.meta?.year ?? 'n.d.'} · {degreeOf.get(hn.id) ?? 0} connections
          </p>
          {#if hn.meta?.apa_reference}
            <p class="mt-1 max-w-56 text-[10px] leading-snug text-slate-500">
              {hn.meta.apa_reference}
            </p>
          {/if}
        {:else}
          <p class="mt-0.5 text-slate-400">{hn.weight} chunks · {degreeOf.get(hn.id) ?? 0} connections</p>
        {/if}
      {/if}
    </div>

    {#if selectedNode}
      <div class="absolute bottom-3 left-3 z-10 max-h-[75%] w-80 overflow-y-auto rounded-xl border border-white/10 bg-slate-900/85 p-3 shadow-xl backdrop-blur">
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0">
            <p class="truncate text-sm font-medium text-slate-100">{selectedNode.label}</p>
            {#if papersModeOn}
              <p class="mt-0.5 text-xs text-slate-400">
                {selectedNode.meta?.year ?? 'n.d.'} · {selectedNode.meta?.authors?.length ?? 0} authors · {degreeOf.get(selectedNode.id) ?? 0} connections
              </p>
              {#if selectedNode.cluster && clusterLabel(selectedNode.cluster)}
                <p class="mt-0.5 text-[11px] font-medium" style="color: {clusterColor(selectedNode.cluster)}">
                  {clusterLabel(selectedNode.cluster)}
                </p>
              {/if}
            {:else}
              <p class="mt-0.5 text-xs text-slate-400">
                {selectedNode.weight} chunks · {degreeOf.get(selectedNode.id) ?? 0} connections
              </p>
            {/if}
          </div>
          <button
            onclick={() => (selected = null)}
            class="shrink-0 text-slate-500 hover:text-slate-200"
            aria-label="Dismiss selection"
          >✕</button>
        </div>
        {#if papersModeOn && selectedNode.meta}
          {@const meta = selectedNode.meta}
          <div class="mt-2 space-y-1.5 border-t border-white/10 pt-2 text-xs text-slate-300">
            {#if meta.authors?.length}
              <p class="leading-snug"><span class="text-slate-500">Authors: </span>{meta.authors.join('; ')}</p>
            {/if}
            {#if meta.year}
              <p><span class="text-slate-500">Year: </span>{meta.year}</p>
            {/if}
            {#if meta.verification_status}
              <p>
            {#if meta.verification_status === 'verified'}
              <span class="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] font-medium text-emerald-300">✓ Verified metadata</span>
            {:else if meta.verification_status === 'ai'}
              <span class="rounded-full bg-sky-500/15 px-2 py-0.5 text-[10px] font-medium text-sky-300">AI-extracted — review</span>
            {:else}
              <span class="rounded-full bg-amber-500/15 px-2 py-0.5 text-[10px] font-medium text-amber-300">⚠ Unverified metadata</span>
            {/if}
              </p>
            {/if}
            {#if meta.doi}
              <p class="break-all"><span class="text-slate-500">DOI: </span>{meta.doi}</p>
            {/if}
            {#if meta.abstract}
              <p class="leading-snug"><span class="text-slate-500">Abstract: </span>{meta.abstract}</p>
            {/if}
            {#if meta.apa_reference}
              <p class="leading-snug"><span class="text-slate-500">APA: </span>{meta.apa_reference}</p>
            {/if}
          </div>
          {#if onEditMeta || onOpenPdf}
            <div class="mt-2 flex gap-2 border-t border-white/10 pt-2">
              {#if onOpenPdf}
                <button
                  onclick={() => onOpenPdf(selectedNode.id)}
                  class="flex-1 rounded-lg bg-indigo-500/90 px-2 py-1.5 text-xs font-medium text-white hover:bg-indigo-400"
                >
                  Open PDF
                </button>
              {/if}
              {#if onEditMeta}
                <button
                  onclick={() => onEditMeta(selectedNode.id)}
                  class="flex-1 rounded-lg border border-white/15 px-2 py-1.5 text-xs font-medium text-slate-200 hover:bg-white/10"
                >
                  Edit metadata
                </button>
              {/if}
            </div>
          {/if}
        {/if}
        {#if selectedNeighbors.length}
          <p class="mb-1 mt-2 text-[10px] font-medium uppercase tracking-wider text-slate-500">
            Connected to
          </p>
          <ul class="space-y-0.5">
            {#each selectedNeighbors as { node, weight } (node.id)}
              <li>
                <button
                  onclick={() => (selected = node.id)}
                  class="flex w-full items-center justify-between gap-2 rounded px-1.5 py-0.5 text-left text-xs text-slate-300 hover:bg-white/5 hover:text-white"
                >
                  <span class="truncate">{node.label}</span>
                  <span class="shrink-0 text-slate-500">{weight}</span>
                </button>
              </li>
            {/each}
          </ul>
        {/if}
        {#if !papersModeOn}
        <div class="mt-2 border-t border-white/10 pt-2">
          <p class="mb-1 text-[10px] font-medium uppercase tracking-wider text-slate-500">
            What the papers say
          </p>
          {#if summary.status === 'loading'}
            <p class="text-xs text-slate-400">Generating summary…</p>
          {:else if summary.status === 'error'}
            <p class="text-xs text-red-400">{summary.error}</p>
          {:else}
            {#if summary.text}
              <p class="text-xs leading-relaxed text-slate-300">{summary.text}</p>
            {/if}
          {/if}
          {#if summary.sources.length > 0}
            <p class="mb-1 mt-2 text-[10px] font-medium uppercase tracking-wider text-slate-500">Sources</p>
            <ul class="space-y-1">
              {#each summary.sources as s (s?.doc_id ?? s?.title ?? s?.snippet ?? '')}
                <li class="flex items-start justify-between gap-2 text-[11px] text-slate-400">
                  <span class="truncate" title={s?.snippet ?? ''}>{s?.title ?? 'Untitled document'}</span>
                  {#if s?.page}
                    <span class="shrink-0 text-slate-500">p. {s.page}</span>
                  {/if}
                </li>
              {/each}
            </ul>
          {/if}
        </div>
        {/if}
      </div>
    {/if}
  </div>
{/if}

<style>
  .node {
    cursor: grab;
    transition:
      translate 0.5s cubic-bezier(0.22, 1, 0.36, 1),
      scale 0.25s ease,
      opacity 0.12s ease;
  }

  .node:hover {
    --s: 1.07;
  }

  .node:focus-visible {
    outline: none;
  }

  .node:focus-visible circle:nth-of-type(2) {
    stroke: #fbbf24;
    stroke-width: 2;
  }

  .node.dragging {
    cursor: grabbing;
    --s: 1.12;
    transition: none;
  }
</style>
