<script lang="ts">
  import { onMount } from 'svelte';
  import StatusBadge from '$lib/core/components/StatusBadge.svelte';
  import { uploadQueue, type UploadItem } from '../store';
  import { getIngestionStatus, pauseIngestion, resumeIngestion, reprocessIngestion } from '../api';

  const items = $derived($uploadQueue);

  const ACTIVE = ['queued', 'processing', 'paused'];

  async function poll() {
    const active = items.filter((i) => i.documentId && ACTIVE.includes(i.status));
    for (const item of active) {
      try {
        const st = await getIngestionStatus(item.documentId!);
        if (st.status === 'indexed') {
          uploadQueue.patch(item.id, { status: 'done', progress: 100, error: undefined });
        } else if (st.status === 'failed') {
          uploadQueue.patch(item.id, { status: 'error', error: st.error || 'Processing failed' });
        } else if (st.status === 'paused') {
          uploadQueue.patch(item.id, { status: 'paused', progress: st.progress });
        } else {
          uploadQueue.patch(item.id, {
            status: st.status === 'queued' ? 'queued' : 'processing',
            progress: st.progress,
          });
        }
      } catch {
        // transient polling failure; try again next tick
      }
    }
  }

  onMount(() => {
    poll();
    const timer = setInterval(poll, 1500);
    return () => clearInterval(timer);
  });

  async function run(fn: () => Promise<unknown>, item: UploadItem) {
    try {
      await fn();
    } catch (err) {
      uploadQueue.patch(item.id, { error: (err as Error).message });
    }
  }

  function pause(item: UploadItem) {
    run(async () => {
      await pauseIngestion(item.documentId!);
      uploadQueue.patch(item.id, { status: 'paused' });
    }, item);
  }

  function resume(item: UploadItem) {
    run(async () => {
      await resumeIngestion(item.documentId!);
      uploadQueue.patch(item.id, { status: 'processing' });
    }, item);
  }

  function reprocess(item: UploadItem) {
    run(async () => {
      await reprocessIngestion(item.documentId!);
      uploadQueue.patch(item.id, { status: 'queued', progress: 0, error: undefined });
    }, item);
  }
</script>

{#if items.length > 0}
  <div class="space-y-2">
    {#each items as item (item.id)}
      <div class="rounded-lg border border-slate-200 p-3">
        <div class="flex items-center gap-3">
          <span class="min-w-0 flex-1 truncate text-sm font-medium text-slate-800">{item.name}</span>
          <StatusBadge status={item.status === 'done' ? 'indexed' : item.status === 'error' ? 'failed' : item.status} />
          <div class="flex items-center gap-1">
            {#if item.status === 'queued' || item.status === 'processing'}
              {#if item.documentId}
                <button
                  onclick={() => pause(item)}
                  class="rounded px-2 py-1 text-xs text-amber-600 hover:bg-amber-50"
                  title="Pause"
                >
                  ⏸ Pause
                </button>
              {/if}
            {:else if item.status === 'paused'}
              {#if item.documentId}
                <button
                  onclick={() => resume(item)}
                  class="rounded px-2 py-1 text-xs text-indigo-600 hover:bg-indigo-50"
                  title="Resume"
                >
                  ▶ Continue
                </button>
              {/if}
            {:else if item.documentId}
              <button
                onclick={() => reprocess(item)}
                class="rounded px-2 py-1 text-xs text-slate-500 hover:bg-slate-100"
                title="Reprocess"
              >
                ↻ Reprocess
              </button>
            {/if}
            <button
              onclick={() => uploadQueue.remove(item.id)}
              class="rounded px-1.5 py-1 text-xs text-slate-400 hover:text-red-500"
              title="Dismiss"
            >
              ✕
            </button>
          </div>
        </div>
        {#if item.progress > 0 && item.status !== 'done'}
          <div class="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
            <div class="h-full rounded-full bg-indigo-500 transition-all" style="width: {item.progress}%"></div>
          </div>
        {/if}
        {#if item.error}
          <p class="mt-1 text-xs text-red-500">{item.error}</p>
        {/if}
      </div>
    {/each}
  </div>
{/if}
