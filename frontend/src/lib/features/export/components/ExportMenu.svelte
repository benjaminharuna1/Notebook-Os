<script lang="ts">
  import { toasts } from '$lib/core/stores/toasts';
  import { exportDossier, exportReferences, type ExportFormat } from '../api';

  let { projectId }: { projectId: string } = $props();

  let open = $state(false);
  let busy = $state('');

  const options = [
    {
      key: 'dossier',
      label: 'Dossier',
      hint: 'Cover page, references and paper notes. Excel gives one row per paper.',
      run: (format: ExportFormat) => exportDossier(projectId, format),
    },
    {
      key: 'references',
      label: 'References',
      hint: 'The compiled APA bibliography on its own, alphabetised and de-duplicated.',
      run: (format: ExportFormat) => exportReferences(projectId, format),
    },
  ];

  async function run(key: string, format: ExportFormat) {
    if (busy || !projectId) return;
    const option = options.find((o) => o.key === key);
    if (!option) return;
    open = false;
    busy = `${key}:${format}`;
    try {
      const filename = await option.run(format);
      toasts.add(`Exported ${filename}`, 'success');
    } catch (e) {
      toasts.add(e instanceof Error ? e.message : 'Export failed', 'error');
    } finally {
      busy = '';
    }
  }
</script>

{#snippet formatButton(key: string, format: ExportFormat, label: string)}
  <button
    type="button"
    onclick={() => run(key, format)}
    disabled={busy !== ''}
    title={label}
    class="flex items-center gap-1.5 rounded-md border border-slate-200 px-2 py-1 text-xs font-medium text-slate-600 hover:border-indigo-300 hover:bg-indigo-50 hover:text-indigo-700 disabled:cursor-not-allowed disabled:opacity-40"
  >
    {#if busy === `${key}:${format}`}
      <span class="h-3 w-3 animate-spin rounded-full border-2 border-slate-300 border-t-indigo-600"
      ></span>
    {:else if format === 'docx'}
      <svg
        viewBox="0 0 16 16"
        class="h-3.5 w-3.5"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <path d="M9.5 1.5h-5a1 1 0 0 0-1 1v11a1 1 0 0 0 1 1h7a1 1 0 0 0 1-1V5.5l-4-4Z" />
        <path d="M9.5 1.5v4h4" />
        <path d="M5.5 9h5M5.5 11.5h5" />
      </svg>
    {:else}
      <svg
        viewBox="0 0 16 16"
        class="h-3.5 w-3.5"
        fill="none"
        stroke="currentColor"
        stroke-width="1.5"
        stroke-linejoin="round"
        aria-hidden="true"
      >
        <rect x="2" y="3" width="12" height="10" rx="1" />
        <path d="M2 6.5h12M6.5 3v10" />
      </svg>
    {/if}
    {label}
  </button>
{/snippet}

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
      class="absolute right-0 z-20 mt-1 w-80 rounded-lg border border-slate-200 bg-white p-1 shadow-lg"
    >
      {#each options as option (option.key)}
        <div class="rounded-md px-3 py-2 hover:bg-slate-50">
          <p class="text-sm font-medium text-slate-800">{option.label}</p>
          <p class="mb-2 text-xs text-slate-500">{option.hint}</p>
          <div class="flex gap-2">
            {@render formatButton(option.key, 'docx', 'Word')}
            {@render formatButton(option.key, 'xlsx', 'Excel')}
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>
