<script lang="ts">
  import { page } from '$app/stores';
  import KnowledgeGraph from '$lib/features/graph/components/KnowledgeGraph.svelte';

  const projectId = $derived($page.params.id);
</script>

<div class="flex h-full flex-col">
  <div class="flex-1 overflow-auto p-6">
    <h1 class="mb-6 text-xl font-bold text-slate-900">Knowledge Graph</h1>
    <KnowledgeGraph projectId={projectId} />
  </div>
</div>
