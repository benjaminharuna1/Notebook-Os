<script lang="ts">
  import { page } from '$app/stores';
  import { search } from '$lib/features/search/api';
  import type { SearchResult } from '$lib/features/search/types';

  const projectId = $derived($page.params.id);

  let query = $state('');
  let results = $state<SearchResult[]>([]);
  let searched = $state(false);

  async function handleSearch() {
    if (!query.trim()) return;
    results = (await search(query, projectId)).results;
    searched = true;
  }
</script>

<div class="flex h-full flex-col">
  <div class="flex-1 overflow-auto p-6">
    <div class="mb-6 flex gap-3">
      <input
        bind:value={query}
        placeholder="Search within this project..."
        class="flex-1 rounded-xl border border-slate-300 px-4 py-3 text-sm outline-none focus:border-indigo-500"
      />
      <button
        onclick={handleSearch}
        class="rounded-xl bg-indigo-600 px-6 py-3 text-sm font-medium text-white hover:bg-indigo-700"
      >
        Search
      </button>
    </div>

    {#if searched && results.length === 0}
      <p class="text-slate-400">No matches in this project.</p>
    {/if}

    <div class="space-y-4">
      {#each results as result (result.chunk_id)}
        <div class="rounded-lg border border-slate-200 p-4">
          <p class="text-sm text-slate-700">{result.content}</p>
          <div class="mt-2 flex items-center gap-2 text-xs text-slate-400">
            <a
              href="/projects/{projectId}/library/{result.document_id}"
              class="font-medium text-indigo-600 hover:text-indigo-800"
            >
              {result.document_title}
            </a>
            <span>Score: {result.score.toFixed(2)}</span>
            {#if result.page_number}
              <span>Page {result.page_number}</span>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  </div>
</div>
