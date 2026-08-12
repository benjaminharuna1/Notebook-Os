<script lang="ts">
  import Header from '$lib/core/components/layout/Header.svelte';
  import DocumentList from '$lib/features/documents/components/DocumentList.svelte';
</script>

<div class="flex h-full flex-col">
  <Header />
  <div class="flex-1 overflow-auto p-6">
    <h1 class="mb-6 text-2xl font-bold text-slate-900">Document Library</h1>
    <DocumentList />
  </div>
</div>
