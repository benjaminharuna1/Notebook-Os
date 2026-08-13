<script lang="ts">
  import { goto } from '$app/navigation';
  import ChatMessage from './ChatMessage.svelte';
  import ChatInput from './ChatInput.svelte';
  import { messages, streaming } from '../store';
  import { streamChat, getSession } from '../api';
  import { toasts } from '$lib/core/stores/toasts';
  import type { ChatMessage as ChatMessageType } from '../types';

  let { sessionId: urlSessionId }: { sessionId?: string } = $props();

  let sessionId = $state<string | null>(null);

  async function loadSession(sid: string) {
    try {
      const data = await getSession(sid);
      messages.set(data.messages);
    } catch {
      toasts.add('Could not load session', 'error');
    }
  }

  $effect(() => {
    if (urlSessionId) {
      if (urlSessionId !== sessionId) {
        sessionId = urlSessionId;
        loadSession(urlSessionId);
      }
    } else {
      sessionId = null;
      messages.set([]);
    }
  });

  function failAssistant(error: Error) {
    streaming.set(false);
    messages.update((m) => {
      const last = m[m.length - 1];
      if (last && last.role === 'assistant') {
        last.content = `⚠️ ${error.message}`;
      }
      return m;
    });
    toasts.add(error.message, 'error');
  }

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
        if (sid) {
          if (!sessionId) sessionId = sid;
          if (urlSessionId !== sid) goto(`/chat/${sid}`);
        }
      },
      failAssistant,
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
    {#if $messages.length === 0}
      <div class="flex h-full items-center justify-center text-slate-400">
        Ask a question about your documents to get started.
      </div>
    {/if}
  </div>
  <ChatInput onsend={sendMessage} disabled={$streaming} />
</div>
