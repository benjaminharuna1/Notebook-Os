<script lang="ts">
  import { actions, pauseAction, resumeAction } from '$lib/features/actions/store';
  import type { ActionInfo } from '$lib/features/actions/types';

  let open = $state(false);

  const all = $derived($actions ?? []);
  const active = $derived(all.filter((a) => a.status === 'queued' || a.status === 'running' || a.status === 'paused'));
  const isBusy = $derived(active.some((a) => a.status === 'running'));

  $effect(() => {
    if (active.length === 0) open = false;
  });

  function kindLabel(kind: string): string {
    switch (kind) {
      case 'literature':
        return 'Literature map';
      case 'graph':
        return 'Knowledge graph';
      default:
        return kind;
    }
  }

  function statusClass(status: ActionInfo['status']): string {
    switch (status) {
      case 'paused':
        return 'bg-amber-100 text-amber-700';
      case 'running':
        return 'bg-emerald-100 text-emerald-700';
      case 'queued':
        return 'bg-slate-200 text-slate-600';
      default:
        return 'bg-slate-200 text-slate-600';
    }
  }

  function statusLabel(status: ActionInfo['status']): string {
    switch (status) {
      case 'paused':
        return 'Paused';
      case 'queued':
        return 'Queued';
      case 'running':
        return 'Running';
      default:
        return status;
    }
  }

  async function toggle(a: ActionInfo) {
    try {
      if (a.status === 'paused') await resumeAction(a.id);
      else if (a.status === 'queued' || a.status === 'running') await pauseAction(a.id);
    } catch {
      // keep the dock usable; the store refresh on the next poll corrects state
    }
  }
</script>

{#if active.length > 0}
  <div class="fixed bottom-4 right-4 z-50 flex flex-col items-end">
    {#if open}
      <div class="mb-2 w-80 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-2xl">
        <div class="flex items-center justify-between border-b border-slate-100 px-4 py-2.5">
          <p class="text-sm font-semibold text-slate-800">Running actions</p>
          <button
            onclick={() => (open = false)}
            aria-label="Close actions panel"
            class="rounded p-1 text-slate-400 hover:text-slate-700"
          >✕</button>
        </div>
        <div class="max-h-80 space-y-3 overflow-y-auto p-3">
          {#each active as a (a.id)}
            <div class="rounded-xl border border-slate-100 bg-slate-50 p-3">
              <div class="mb-1 flex items-center justify-between gap-2">
                <p class="truncate text-xs font-medium text-slate-800" title={a.title}>{a.title}</p>
                <span class="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium {statusClass(a.status)}">
                  {statusLabel(a.status)}
                </span>
              </div>
              <p class="mb-1.5 text-[10px] text-slate-400">{kindLabel(a.kind)}</p>
              <div class="h-1.5 overflow-hidden rounded-full bg-slate-200">
                <div
                  class="h-full rounded-full bg-indigo-500 transition-all duration-300"
                  style="width: {Math.min(100, Math.max(0, a.progress ?? 0))}%"
                ></div>
              </div>
              <div class="mt-1.5 flex items-center justify-between gap-2">
                <p class="min-w-0 truncate text-[10px] text-slate-500">
                  {Math.round(a.progress ?? 0)}% · {a.stage ?? 'Working'}
                </p>
                <button
                  onclick={() => toggle(a)}
                  class="shrink-0 rounded-md border border-slate-300 bg-white px-2 py-0.5 text-[10px] font-medium text-slate-600 hover:bg-slate-100"
                >
                  {a.status === 'paused' ? '▶ Continue' : '⏸ Pause'}
                </button>
              </div>
            </div>
          {/each}
        </div>
      </div>
    {/if}
    <button
      onclick={() => (open = !open)}
      aria-label="Show running actions"
      aria-expanded={open}
      class="relative flex items-center gap-2 rounded-full border border-slate-200 bg-white py-2 pl-3.5 pr-2.5 text-sm font-medium text-slate-700 shadow-lg hover:bg-slate-50"
    >
      {#if isBusy}
        <span class="relative flex h-2.5 w-2.5">
          <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-indigo-400 opacity-75"></span>
          <span class="relative inline-flex h-2.5 w-2.5 rounded-full bg-indigo-500"></span>
        </span>
      {:else}
        <span class="inline-block h-2.5 w-2.5 rounded-full bg-amber-500"></span>
      {/if}
      <span>Actions</span>
      <span class="rounded-full bg-indigo-600 px-1.5 py-0.5 text-[10px] font-bold text-white">{active.length}</span>
    </button>
  </div>
{/if}
