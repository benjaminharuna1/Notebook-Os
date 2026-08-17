<script lang="ts">
  let {
    onsend,
    onStop,
    disabled = false,
    isStreaming = false,
  }: {
    onsend: (text: string, slashCommand?: string) => void;
    onStop?: () => void;
    disabled?: boolean;
    isStreaming?: boolean;
  } = $props();

  let text = $state('');
  let slashOpen = $state(false);
  let slashSearch = $state('');

  const SLASH_COMMANDS = [
    { cmd: '/summarize', label: 'Summarize project', desc: 'Full summary of all literature' },
    { cmd: '/evaluate', label: 'Evaluate literature', desc: 'Critical assessment of methods & gaps' },
    { cmd: '/mapping', label: 'Literature mapping', desc: 'Thematic grouping & connections' },
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
    }
  }

  function selectSlash(cmd: string) {
    text = cmd + ' ';
    slashOpen = false;
    slashSearch = '';
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

    <div class="flex gap-3">
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
          class="self-end rounded-xl border border-red-300 bg-white px-6 py-3 text-sm font-medium text-red-600 hover:bg-red-50"
        >
          Stop
        </button>
      {:else}
        <button
          onclick={handleSubmit}
          {disabled}
          class="self-end rounded-xl bg-indigo-600 px-6 py-3 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          Send
        </button>
      {/if}
    </div>
  </div>
</div>
