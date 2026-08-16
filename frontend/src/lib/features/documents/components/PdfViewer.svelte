<script lang="ts">
  import { untrack } from 'svelte';
  import { getDocumentFileUrl } from '$lib/features/literature/api';

  let {
    projectId = '',
    documentId = '',
    title = 'Document preview',
    fileType = 'pdf',
  }: {
    projectId?: string | null;
    documentId?: string | null;
    title?: string | null;
    fileType?: string | null;
  } = $props();

  let url = $state<string | null>(null);
  let error = $state<string | null>(null);
  let loading = $state(true);

  const isPdf = $derived((fileType ?? '').toLowerCase() === 'pdf');

  $effect(() => {
    const pid = projectId;
    const did = documentId;
    const previous = untrack(() => url);
    url = null;
    error = null;
    loading = true;
    if (previous) URL.revokeObjectURL(previous);
    if (!pid || !did) {
      loading = false;
      return;
    }
    getDocumentFileUrl(pid, did)
      .then((blobUrl) => {
        url = blobUrl;
        loading = false;
      })
      .catch((e) => {
        error = e instanceof Error ? e.message : 'Could not load the document';
        loading = false;
      });
  });
</script>

<div class="flex h-full flex-col">
  {#if loading}
    <div class="flex flex-1 items-center justify-center text-sm text-slate-400">
      Loading document…
    </div>
  {:else if error}
    <div class="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center">
      <p class="text-sm text-red-400">{error}</p>
    </div>
  {:else if url}
    {#if isPdf}
      <iframe
        src={url}
        title={title}
        class="h-full w-full flex-1 border-0 bg-slate-100"
        loading="lazy"
      ></iframe>
    {:else}
      <div class="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
        <p class="text-sm text-slate-400">
          In-browser preview is only available for PDFs. Download the file to open it in its
          native app.
        </p>
        <a
          href={url}
          download
          class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-500"
        >
          Download file
        </a>
      </div>
    {/if}
  {:else}
    <div class="flex flex-1 items-center justify-center text-sm text-slate-400">
      No document to display.
    </div>
  {/if}
</div>
