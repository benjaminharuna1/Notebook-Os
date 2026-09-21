<script lang="ts">
  import { toasts } from '$lib/core/stores/toasts';
  import { exportDossier, exportWorkbook } from '../api';

  let { projectId }: { projectId: string } = $props();

  let open = $state(false);
  let busy = $state<'workbook' | 'dossier' | ''>('');
  let includeAnswers = $state(false);

  async function run(kind: 'workbook' | 'dossier') {
    if (busy || !projectId) return;
    open = false;
    busy = kind;
    try {
      const filename =
        kind === 'workbook'
          ? await exportWorkbook(projectId)
          : await exportDossier(projectId, includeAnswers);
      toasts.add(`Exported ${filename}`, 'success');
    } catch (e) {
      toasts.add(e instanceof Error ? e.message : 'Export failed', 'error');
    } finally {
      busy = '';
    }
  }
</script>

<div class="relative">
  <button
    type="button"
    onclick={() => (open = !open)}
    disabled={busy !== ''}
    class="flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50"
  >
    {#if busy}
      <span
        class="h-3 w-3 animate-spin rounded-full border-2 border-slate-300 border-t-indigo-600"
      ></span>
      Exporting…
    {:else}
      ⇩ Export
    {/if}
  </button>

  {#if open}
    <button
      type="button"
      aria-label="Close export menu"
      class="fixed inset-0 z-10 cursor-default"
      onclick={() => (open = false)}
    ></button>
    <div
      class="absolute right-0 z-20 mt-1 w-72 rounded-lg border border-slate-200 bg-white p-1 shadow-lg"
    >
      <button
        type="button"
        onclick={() => run('workbook')}
        class="block w-full rounded-md px-3 py-2 text-left hover:bg-slate-50"
      >
        <span class="block text-sm font-medium text-slate-800">Literature workbook</span>
        <span class="block text-xs text-slate-500">
          One row per paper, with metadata provenance. (.xlsx)
        </span>
      </button>
      <button
        type="button"
        onclick={() => run('dossier')}
        class="block w-full rounded-md px-3 py-2 text-left hover:bg-slate-50"
      >
        <span class="block text-sm font-medium text-slate-800">Project dossier</span>
        <span class="block text-xs text-slate-500">
          References and reading notes, with what is missing stated up front. (.docx)
        </span>
      </button>
      <label
        class="flex items-center gap-2 rounded-md px-3 py-2 text-xs text-slate-600 hover:bg-slate-50"
      >
        <input type="checkbox" bind:checked={includeAnswers} class="rounded border-slate-300" />
        Include saved answers
      </label>
    </div>
  {/if}
</div>
