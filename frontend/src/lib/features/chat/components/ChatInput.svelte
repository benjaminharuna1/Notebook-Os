<script lang="ts">
  let { onsend, disabled = false }: { onsend: (text: string) => void; disabled?: boolean } = $props();

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
      class="flex-1 resize-none rounded-xl border border-slate-300 px-4 py-3 text-sm outline-none focus:border-indigo-500"
    />
    <button
      onclick={handleSubmit}
      {disabled}
      class="self-end rounded-xl bg-indigo-600 px-6 py-3 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
    >
      Send
    </button>
  </div>
</div>
