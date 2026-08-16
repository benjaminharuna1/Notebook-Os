<script lang="ts">
  import { page } from '$app/stores';
  import Header from '$lib/core/components/layout/Header.svelte';
  import { getProject } from '$lib/features/projects/api';
  import { toasts } from '$lib/core/stores/toasts';
  import type { Project } from '$lib/features/projects/types';

  let { children }: { children?: import('svelte').Snippet } = $props();

  let project = $state<Project | null>(null);
  let notFound = $state(false);

  const projectId = $derived($page.params.id);
  const active = $derived.by(() => {
    const p = $page.url.pathname;
    if (p.includes('/search')) return 'search';
    if (p.includes('/chat')) return 'chat';
    if (p.includes('/graph')) return 'graph';
    if (p.includes('/literature')) return 'literature';
    return 'library';
  });

  $effect(() => {
    project = null;
    notFound = false;
    getProject(projectId)
      .then((p) => (project = p))
      .catch(() => (notFound = true));
  });
</script>

<div class="flex h-full flex-col">
  <Header />
  {#if notFound}
    <div class="flex flex-1 items-center justify-center text-slate-400">Project not found</div>
  {:else}
    <div class="border-b border-slate-200 px-6 py-3">
      <h1 class="text-lg font-bold text-slate-900">{project?.name ?? 'Loading...'}</h1>
      {#if project?.description}
        <p class="truncate text-sm text-slate-500">{project.description}</p>
      {/if}
      <nav class="mt-2 flex gap-5 text-sm">
        <a
          href="/projects/{projectId}/library"
          class="pb-1 {active === 'library'
            ? 'border-b-2 border-indigo-600 font-medium text-indigo-600'
            : 'text-slate-500 hover:text-slate-800'}"
        >
          Library
        </a>
        <a
          href="/projects/{projectId}/search"
          class="pb-1 {active === 'search'
            ? 'border-b-2 border-indigo-600 font-medium text-indigo-600'
            : 'text-slate-500 hover:text-slate-800'}"
        >
          Search
        </a>
        <a
          href="/projects/{projectId}/chat"
          class="pb-1 {active === 'chat'
            ? 'border-b-2 border-indigo-600 font-medium text-indigo-600'
            : 'text-slate-500 hover:text-slate-800'}"
        >
          Chat
        </a>
        <a
          href="/projects/{projectId}/graph"
          class="pb-1 {active === 'graph'
            ? 'border-b-2 border-indigo-600 font-medium text-indigo-600'
            : 'text-slate-500 hover:text-slate-800'}"
        >
          Graph
        </a>
        <a
          href="/projects/{projectId}/literature"
          class="pb-1 {active === 'literature'
            ? 'border-b-2 border-indigo-600 font-medium text-indigo-600'
            : 'text-slate-500 hover:text-slate-800'}"
        >
          Literature
        </a>
      </nav>
    </div>
    <div class="flex-1 overflow-auto">
      {@render children?.()}
    </div>
  {/if}
</div>
