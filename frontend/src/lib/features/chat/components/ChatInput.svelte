<script lang="ts">
  let {
    onsend,
    onStop,
    disabled = false,
    isStreaming = false,
  }: {
    onsend: (text: string) => void;
    onStop?: () => void;
    disabled?: boolean;
    isStreaming?: boolean;
  } = $props();

  let text = $state('');

  function handleSubmit() {
    if (!text.trim() || disabled) return;
    onsend(text.trim());
    text = '';
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }
</script>

<div class="border-t border-slate-200 p-4">
  <div class="flex gap-3">
    <textarea
      bind:value={text}
      onkeydown={handleKeydown}
      placeholder="Ask a question about your documents..."
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
