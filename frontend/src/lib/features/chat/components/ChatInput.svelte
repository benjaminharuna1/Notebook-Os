<script lang="ts">
  import FileDropzone from '$lib/features/ingestion/components/FileDropzone.svelte';
  import UploadQueue from '$lib/features/ingestion/components/UploadQueue.svelte';

  let {
    onsend,
    onStop,
    disabled = false,
    isStreaming = false,
    projectId,
    availableDocs = [],
    selectedDocIds = new Set(),
    onToggleDoc,
    onClearDocs,
  }: {
    onsend: (text: string, slashCommand?: string) => void;
    onStop?: () => void;
    disabled?: boolean;
    isStreaming?: boolean;
    projectId?: string;
    availableDocs?: { id: string; title: string }[];
    selectedDocIds?: Set<string>;
    onToggleDoc?: (docId: string) => void;
    onClearDocs?: () => void;
  } = $props();

  let text = $state('');
  let slashOpen = $state(false);
  let slashSearch = $state('');
  let docSearch = $state('');
  let attachOpen = $state(false);
  let attachTab = $state<'upload' | 'papers'>('upload');

  const SLASH_COMMANDS = [
    { cmd: '/summarize', label: 'Summarize project', desc: 'Full summary of all literature' },
    { cmd: '/evaluate', label: 'Evaluate literature', desc: 'Critical assessment of methods & gaps' },
    { cmd: '/mapping', label: 'Literature mapping', desc: 'Thematic grouping & connections' },
    { cmd: '/review', label: 'Peer review', desc: 'Adversarial audit: flaws, biases, counter-narratives' },
  ];

  const filteredSlash = $derived(
    slashSearch
      ? SLASH_COMMANDS.filter(
          (c) =>
            c.cmd.includes(slashSearch.toLowerCase()) ||
            c.label.toLowerCase().includes(slashSearch.toLowerCase())
        )
      : SLASH_COMMANDS
  );

  const filteredDocs = $derived(
    docSearch
      ? availableDocs.filter((d) => d.title.toLowerCase().includes(docSearch.toLowerCase()))
      : availableDocs
  );

  function handleSubmit() {
    if (!text.trim() || disabled) return;
    const trimmed = text.trim();
    const slashMatch = trimmed.match(/^\/\w+/);
    if (slashMatch) {
      onsend(trimmed, slashMatch[0].toLowerCase());
    } else {
      onsend(trimmed);
    }
    text = '';
    slashOpen = false;
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
    if (e.key === 'Escape') {
      slashOpen = false;
      attachOpen = false;
    }
  }

  function selectSlash(cmd: string) {
    text = cmd + ' ';
    slashOpen = false;
    slashSearch = '';
  }

  function toggleAttach() {
    attachOpen = !attachOpen;
    if (attachOpen) attachTab = 'upload';
  }

  $effect(() => {
    const val = text.trim();
    if (val.startsWith('/')) {
      slashOpen = true;
      slashSearch = val;
    } else {
      slashOpen = false;
      slashSearch = '';
    }
  });
</script>

<div class="border-t border-slate-200 p-4">
  <div class="relative">
    {#if slashOpen && filteredSlash.length > 0}
      <div class="absolute bottom-full left-0 mb-2 w-72 rounded-xl border border-slate-200 bg-white p-1.5 shadow-lg">
        {#each filteredSlash as item}
          <button
            onclick={() => selectSlash(item.cmd)}
            class="flex w-full flex-col rounded-lg px-3 py-2 text-left hover:bg-slate-50"
          >
            <span class="text-xs font-medium text-slate-800">{item.cmd}</span>
            <span class="text-[10px] text-slate-500">{item.desc}</span>
          </button>
        {/each}
      </div>
    {/if}

    {#if attachOpen}
      <div class="absolute bottom-full left-0 mb-2 w-96 rounded-xl border border-slate-200 bg-white shadow-lg">
        <div class="flex border-b border-slate-200">
          <button
            onclick={() => (attachTab = 'upload')}
            class="flex-1 px-4 py-2.5 text-xs font-medium {attachTab === 'upload'
              ? 'border-b-2 border-indigo-600 text-indigo-600'
              : 'text-slate-500 hover:text-slate-700'}"
          >
            Upload PDFs
          </button>
          <button
            onclick={() => (attachTab = 'papers')}
            class="flex-1 px-4 py-2.5 text-xs font-medium {attachTab === 'papers'
              ? 'border-b-2 border-indigo-600 text-indigo-600'
              : 'text-slate-500 hover:text-slate-700'}"
          >
            Select Papers
          </button>
        </div>
        <div class="max-h-80 overflow-y-auto p-3">
          {#if attachTab === 'upload'}
            <FileDropzone {projectId} />
            <div class="mt-3">
              <UploadQueue />
            </div>
          {:else}
            <div class="mb-2 flex items-center justify-between">
              <span class="text-[11px] font-medium text-slate-500">
                {selectedDocIds.size === 0 ? 'All papers' : `${selectedDocIds.size} selected`}
              </span>
              {#if selectedDocIds.size > 0}
                <button
                  onclick={onClearDocs}
                  class="text-[10px] text-slate-400 hover:text-slate-600"
                >
                  Clear
                </button>
              {/if}
            </div>
            <input
              bind:value={docSearch}
              placeholder="Search papers..."
              class="mb-2 w-full rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs outline-none focus:border-indigo-400"
            />
            <div class="max-h-56 overflow-y-auto">
              {#each filteredDocs as doc}
                <label class="flex cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-xs hover:bg-slate-50">
                  <input
                    type="checkbox"
                    checked={selectedDocIds.has(doc.id)}
                    onchange={() => onToggleDoc?.(doc.id)}
                    class="h-3 w-3 rounded accent-indigo-600"
                  />
                  <span class="truncate text-slate-700">{doc.title}</span>
                </label>
              {/each}
              {#if filteredDocs.length === 0}
                <p class="px-2 py-3 text-center text-[11px] text-slate-400">No papers found</p>
              {/if}
            </div>
          {/if}
        </div>
      </div>
    {/if}

    <div class="flex gap-2">
      <button
        onclick={toggleAttach}
        class="relative flex h-11 w-11 shrink-0 items-center justify-center self-end rounded-xl border border-slate-300 text-slate-400 hover:border-slate-400 hover:text-slate-600 {attachOpen ? 'border-indigo-400 text-indigo-600' : ''}"
        title="Attach files or select papers"
      >
        <svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l8.57-8.57A4 4 0 1 1 18 8.84l-8.59 8.57a2 2 0 0 1-2.83-2.83l8.49-8.48" />
        </svg>
        {#if selectedDocIds.size > 0}
          <span class="absolute -right-1 -top-1 flex h-4 w-4 items-center justify-center rounded-full bg-indigo-600 text-[9px] font-bold text-white">{selectedDocIds.size}</span>
        {/if}
      </button>
      <textarea
        bind:value={text}
        onkeydown={handleKeydown}
        placeholder="Ask a question or type / for commands..."
        rows="1"
        disabled={isStreaming}
        class="flex-1 resize-none rounded-xl border border-slate-300 px-4 py-3 text-sm outline-none focus:border-indigo-500 disabled:opacity-50"
      />
      {#if isStreaming}
        <button
          onclick={() => onStop?.()}
          class="flex h-11 items-center self-end rounded-xl border border-red-300 bg-white px-5 text-sm font-medium text-red-600 hover:bg-red-50"
        >
          Stop
        </button>
      {:else}
        <button
          onclick={handleSubmit}
          {disabled}
          class="flex h-11 items-center self-end rounded-xl bg-indigo-600 px-5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          Send
        </button>
      {/if}
    </div>
  </div>
</div>
