<script lang="ts">
  import ChatMessage from './ChatMessage.svelte';
  import ChatInput from './ChatInput.svelte';
  import { messages, streaming } from '../store';
  import { streamChat, listSessions, getSession } from '../api';
  import type { ChatMessage as ChatMessageType } from '../types';

  let sessionId = $state<string | null>(null);

  async function sendMessage(text: string) {
    const userMsg: ChatMessageType = {
      id: crypto.randomUUID(),
      session_id: sessionId || '',
      role: 'user',
      content: text,
    };
    messages.update((m) => [...m, userMsg]);
    streaming.set(true);

    const assistantMsg: ChatMessageType = {
      id: crypto.randomUUID(),
      session_id: sessionId || '',
      role: 'assistant',
      content: '',
    };
    messages.update((m) => [...m, assistantMsg]);

    streamChat(
      sessionId || undefined,
      text,
      (chunk) => {
        messages.update((m) => {
          const last = m[m.length - 1];
          if (last && last.role === 'assistant') {
            last.content += chunk;
          }
          return m;
        });
      },
      (sid) => {
        streaming.set(false);
        if (!sessionId && sid) sessionId = sid;
      },
      (error) => {
        streaming.set(false);
        console.error(error);
      },
    );
  }

  function scrollToBottom(node: HTMLDivElement) {
    $effect(() => {
      if ($messages.length) {
        node.scrollTop = node.scrollHeight;
      }
    });
  }
</script>

<div class="flex h-full flex-col">
  <div
    class="flex-1 space-y-4 overflow-y-auto p-6"
    use:scrollToBottom
  >
    {#each $messages as msg (msg.id)}
      <ChatMessage message={msg} />
    {/each}
  </div>
  <ChatInput onsend={sendMessage} disabled={$streaming} />
</div>
