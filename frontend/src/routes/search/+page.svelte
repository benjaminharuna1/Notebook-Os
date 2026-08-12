<script lang="ts">
  import Header from '$lib/core/components/layout/Header.svelte';

  let query = $state('');
  let results = $state<any[]>([]);

  async function handleSearch() {
    if (!query.trim()) return;
    const { search } = await import('$lib/features/search/api');
    const res = await search(query);
    results = res.results;
  }
</script>

<div class="flex h-full flex-col">
  <Header />
  <div class="flex-1 overflow-auto p-6">
    <div class="mb-6 flex gap-3">
      <input
        bind:value={query}
        placeholder="Search your documents..."
        class="flex-1 rounded-xl border border-slate-300 px-4 py-3 text-sm outline-none focus:border-indigo-500"
      />
      <button
        onclick={handleSearch}
        class="rounded-xl bg-indigo-600 px-6 py-3 text-sm font-medium text-white hover:bg-indigo-700"
      >
        Search
      </button>
    </div>

    <div class="space-y-4">
      {#each results as result (result.chunk_id)}
        <div class="rounded-lg border border-slate-200 p-4">
          <p class="text-sm text-slate-700">{result.content}</p>
          <div class="mt-2 flex gap-2 text-xs text-slate-400">
            <span>{result.document_title}</span>
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
