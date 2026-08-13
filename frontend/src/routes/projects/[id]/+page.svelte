<script lang="ts">
  import { page } from '$app/stores';
  import FileDropzone from '$lib/features/ingestion/components/FileDropzone.svelte';
  import UploadQueue from '$lib/features/ingestion/components/UploadQueue.svelte';
  import DocumentList from '$lib/features/documents/components/DocumentList.svelte';

  const projectId = $derived($page.params.id);
</script>

<div class="flex h-full">
  <div class="flex-1 overflow-auto p-6">
    <DocumentList projectId={projectId} />
  </div>
  <div class="w-80 space-y-4 border-l border-slate-200 p-4">
    <FileDropzone projectId={projectId} />
    <UploadQueue />
  </div>
</div>
