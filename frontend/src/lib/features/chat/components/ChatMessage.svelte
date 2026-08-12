<script lang="ts">
  import type { ChatMessage } from '../types';
  import Spinner from '$lib/core/components/ui/Spinner.svelte';

  let { message }: { message: ChatMessage } = $props();

  const isUser = $derived(message.role === 'user');
</script>

<div class="flex {isUser ? 'justify-end' : 'justify-start'}">
  <div
    class="max-w-[80%] rounded-2xl px-4 py-3 {isUser
      ? 'bg-indigo-600 text-white'
      : 'bg-slate-100 text-slate-900'}"
  >
    <p class="text-sm whitespace-pre-wrap">
      {message.content}
      {#if !message.content && message.role === 'assistant'}
        <Spinner size="sm" />
      {/if}
    </p>
  </div>
</div>
