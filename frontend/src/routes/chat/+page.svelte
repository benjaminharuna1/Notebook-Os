<script lang="ts">
  import { onMount } from 'svelte';
  import Header from '$lib/core/components/layout/Header.svelte';
  import ChatWindow from '$lib/features/chat/components/ChatWindow.svelte';
  import FileDropzone from '$lib/features/ingestion/components/FileDropzone.svelte';
  import UploadQueue from '$lib/features/ingestion/components/UploadQueue.svelte';
  import { activeModel } from '$lib/features/models/store';
  import { listModels } from '$lib/features/models/api';
  import { getLocalStatus } from '$lib/features/settings/api';
  import type { LocalStatus } from '$lib/features/settings/types';

  let status = $state<LocalStatus | null>(null);
  let showBanner = $state(false);

  onMount(async () => {
    const res = await listModels().catch(() => null);
    if (res) activeModel.set(res.active);
    status = await getLocalStatus().catch(() => null);
    if (status && !status.ollama_running && res?.active?.provider === 'ollama') {
      showBanner = true;
    }
  });
</script>

<div class="flex h-full flex-col">
  <Header />
  {#if showBanner}
    <div class="flex items-center justify-between gap-4 border-b border-amber-200 bg-amber-50 px-6 py-2 text-sm text-amber-800">
      <span>
        Ollama isn't running, but your selected model is local. Start Ollama and pull
        <code class="rounded bg-amber-100 px-1">{status?.recommended_local_model}</code>, or pick a cloud model from
        the selector if you've enabled it.
      </span>
    </div>
  {/if}
  <div class="flex flex-1">
    <div class="flex flex-1 flex-col">
      <ChatWindow />
    </div>
    <div class="w-80 border-l border-slate-200 p-4 space-y-4">
      <FileDropzone />
      <UploadQueue />
    </div>
  </div>
</div>
