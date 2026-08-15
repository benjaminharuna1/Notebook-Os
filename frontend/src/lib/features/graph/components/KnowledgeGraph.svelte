<script lang="ts">
  import { getGraph } from '$lib/features/graph/api';
  import type { GraphResponse } from '$lib/features/graph/types';

  let { projectId }: { projectId?: string } = $props();

  let graph = $state<GraphResponse | null>(null);
  let error = $state('');
  let loading = $state(true);
  let highlighted = $state<string | null>(null);
  let layoutNodes = $state<SimNode[]>([]);
  let layoutEdges = $state<SimEdge[]>([]);

  const W = 800;
  const H = 600;

  interface SimNode {
    id: string;
    label: string;
    weight: number;
    x: number;
    y: number;
    vx: number;
    vy: number;
  }

  interface SimEdge {
    source: string;
    target: string;
    weight: number;
  }

  let maxNodeWeight = $state(1);
  let maxEdgeWeight = $state(1);

  $effect(() => {
    if (!projectId) return;
    loading = true;
    error = '';
    getGraph(projectId)
      .then((g) => {
        graph = g;
        layout(g);
      })
      .catch((e) => (error = (e as Error).message))
      .finally(() => (loading = false));
  });

  function layout(g: GraphResponse) {
    layoutNodes = g.nodes.map((n, i) => {
      const angle = (i / Math.max(g.nodes.length, 1)) * Math.PI * 2;
      return {
        id: n.id,
        label: n.label,
        weight: n.weight,
        x: W / 2 + Math.cos(angle) * 180,
        y: H / 2 + Math.sin(angle) * 180,
        vx: 0,
        vy: 0,
      };
    });
    layoutEdges = g.edges.map((e) => ({ source: e.source, target: e.target, weight: e.weight }));
    maxNodeWeight = Math.max(1, ...layoutNodes.map((n) => n.weight));
    maxEdgeWeight = Math.max(1, ...layoutEdges.map((e) => e.weight));
    simulate();
  }

  function simulate() {
    const nodeById = new Map(layoutNodes.map((n) => [n.id, n]));
    const pairs: [SimNode, SimNode][] = [];
    for (let i = 0; i < layoutNodes.length; i++) {
      for (let j = i + 1; j < layoutNodes.length; j++) {
        pairs.push([layoutNodes[i], layoutNodes[j]]);
      }
    }
    const springs: [SimNode, SimNode][] = [];
    for (const e of layoutEdges) {
      const s = nodeById.get(e.source);
      const t = nodeById.get(e.target);
      if (s && t) springs.push([s, t]);
    }

    const repulsion = 4200;
    const restLength = 120;
    const iterations = 350;

    for (let iter = 0; iter < iterations; iter++) {
      const temperature = 1 - iter / iterations;
      for (const [a, b] of pairs) {
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        let d2 = dx * dx + dy * dy;
        if (d2 < 1) {
          dx = Math.random() - 0.5;
          dy = Math.random() - 0.5;
          d2 = dx * dx + dy * dy;
        }
        const d = Math.sqrt(d2);
        const force = repulsion / d2;
        a.vx -= (dx / d) * force;
        a.vy -= (dy / d) * force;
        b.vx += (dx / d) * force;
        b.vy += (dy / d) * force;
      }
      for (const [a, b] of springs) {
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = (d - restLength) * 0.02;
        a.vx += (dx / d) * force;
        a.vy += (dy / d) * force;
        b.vx -= (dx / d) * force;
        b.vy -= (dy / d) * force;
      }
      for (const n of layoutNodes) {
        n.vx += (W / 2 - n.x) * 0.01;
        n.vy += (H / 2 - n.y) * 0.01;
        n.vx *= 0.85;
        n.vy *= 0.85;
        n.x += n.vx * temperature;
        n.y += n.vy * temperature;
        n.x = Math.min(W - 40, Math.max(40, n.x));
        n.y = Math.min(H - 40, Math.max(40, n.y));
      }
    }
  }

  function nodeRadius(n: SimNode) {
    return 8 + (n.weight / maxNodeWeight) * 14;
  }

  function nodePos(id: string) {
    const n = layoutNodes.find((node) => node.id === id);
    return n ? { x: n.x, y: n.y } : { x: W / 2, y: H / 2 };
  }

  function edgeDim(e: SimEdge) {
    const dimmed = highlighted !== null && e.source !== highlighted && e.target !== highlighted;
    return dimmed ? 0.08 : 0.28 + (e.weight / maxEdgeWeight) * 0.5;
  }

  function nodeDim(n: SimNode) {
    if (highlighted === null || highlighted === n.id) return 1;
    return connectedTo(highlighted, n.id) ? 0.7 : 0.15;
  }

  function connectedTo(a: string, b: string) {
    return layoutEdges.some((e) =>
      (e.source === a && e.target === b) || (e.source === b && e.target === a),
    );
  }

  function truncate(label: string) {
    return label.length > 20 ? `${label.slice(0, 19)}…` : label;
  }
</script>

{#if loading}
  <div class="flex h-64 items-center justify-center text-slate-400">Loading graph...</div>
{:else if error}
  <div class="flex h-64 items-center justify-center rounded-lg bg-red-50 px-4 text-sm text-red-600">{error}</div>
{:else if !graph || graph.nodes.length === 0}
  <div class="flex h-64 items-center justify-center px-4 text-center text-slate-400">
    No knowledge graph yet — upload and index documents in this project.
  </div>
{:else}
  <div class="mb-3 text-xs text-slate-400">
    {graph.nodes.length} concepts · {graph.edges.length} connections
  </div>
  <svg viewBox="0 0 {W} {H}" class="h-full w-full" role="img" aria-label="Knowledge graph">
    {#each layoutEdges as e}
      {@const pos = nodePos(e.source)}
      {@const tpos = nodePos(e.target)}
      <line
        x1={pos.x}
        y1={pos.y}
        x2={tpos.x}
        y2={tpos.y}
        stroke="#94a3b8"
        stroke-width={0.5 + (e.weight / maxEdgeWeight) * 2.5}
        stroke-opacity={edgeDim(e)}
      />
    {/each}
    {#each layoutNodes as n}
      {@const r = nodeRadius(n)}
      <g
        class="cursor-pointer"
        role="group"
        onmouseenter={() => (highlighted = n.id)}
        onmouseleave={() => (highlighted = null)}
      >
        <circle
          cx={n.x}
          cy={n.y}
          r={r}
          fill={highlighted === n.id ? '#4f46e5' : '#818cf8'}
          fill-opacity={nodeDim(n)}
          stroke="#ffffff"
          stroke-width="1.5"
        />
        <text
          x={n.x}
          y={n.y + r + 12}
          text-anchor="middle"
          font-size="11"
          fill="#475569"
          fill-opacity={nodeDim(n)}
        >
          {truncate(n.label)}
        </text>
        <title>{n.label} — {n.weight} chunks</title>
      </g>
    {/each}
  </svg>
{/if}
