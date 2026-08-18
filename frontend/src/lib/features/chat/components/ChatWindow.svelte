<script lang="ts">
  import { goto } from '$app/navigation';
  import ChatMessage from './ChatMessage.svelte';
  import ChatInput from './ChatInput.svelte';
  import { messages, streaming } from '../store';
  import { streamChat, getSession } from '../api';
  import { listDocuments } from '$lib/features/documents/api';
  import { toasts } from '$lib/core/stores/toasts';
  import type { ChatMessage as ChatMessageType, SourceChunk } from '../types';

  let { sessionId: urlSessionId, projectId }: { sessionId?: string; projectId?: string } = $props();

  let sessionId = $state<string | null>(null);
  let abortFn = $state<(() => void) | null>(null);
  let selectedDocIds = $state<Set<string>>(new Set());
  let availableDocs = $state<{ id: string; title: string }[]>([]);

  async function loadSession(sid: string) {
    try {
      const data = await getSession(sid);
      messages.set(data.messages);
    } catch {
      toasts.add('Could not load session', 'error');
    }
  }

  async function loadDocs() {
    if (!projectId) return;
    try {
      const result = await listDocuments({ page: 1, limit: 100, project_id: projectId });
      availableDocs = result.documents.map((d) => ({ id: d.id, title: d.title }));
    } catch {
      availableDocs = [];
    }
  }

  $effect(() => {
    if (projectId) {
      sessionId = null;
      messages.set([]);
      selectedDocIds = new Set();
      loadDocs();
    }
  });

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
    abortFn = null;
    const msg = error?.message || 'An unexpected error occurred';
    messages.update((m) => {
      const last = m[m.length - 1];
      if (last && last.role === 'assistant') {
        // Only show error prefix if the message isn't already an error
        if (!last.content?.startsWith('\u26a0\ufe0f')) {
          last.content = `\u26a0\ufe0f ${msg}`;
        }
      }
      return m;
    });
    toasts.add(msg, 'error');
  }

  function stopStreaming() {
    abortFn?.();
    streaming.set(false);
    abortFn = null;
    toasts.add('Generation stopped.', 'info');
  }

  // --- shared streaming logic ---
  function startStreaming(
    userText: string,
    slashCommand?: string,
    options?: { regenerate?: boolean },
  ) {
    streaming.set(true);

    const assistantMsg: ChatMessageType = {
      id: crypto.randomUUID(),
      session_id: sessionId || '',
      role: 'assistant',
      content: '',
    };
    messages.update((m) => [...m, assistantMsg]);
    const assistantId = assistantMsg.id;

    const docIds = selectedDocIds.size > 0 ? [...selectedDocIds] : undefined;

    abortFn = streamChat(
      sessionId || undefined,
      userText,
      projectId,
      docIds,
      (chunk) => {
        if (chunk == null) return;
        messages.update((m) => {
          const last = m[m.length - 1];
          if (last && last.id === assistantId) {
            last.content += chunk;
          }
          return m;
        });
      },
      (sources: SourceChunk[]) => {
        messages.update((m) => {
          const last = m[m.length - 1];
          if (last && last.id === assistantId) {
            last.sources = sources;
          }
          return m;
        });
      },
      (sid) => {
        streaming.set(false);
        abortFn = null;
        // Fetch model_used from the last assistant message we just populated
        messages.update((m) => {
          const last = m[m.length - 1];
          if (last && last.id === assistantId) {
            // model_used is injected server-side on persist; we won't have it
            // on the live SSE message, but it shows on reload from DB.
          }
          return m;
        });
        if (sid) {
          if (!sessionId) sessionId = sid;
          const path = projectId ? `/projects/${projectId}/chat/${sid}` : `/chat/${sid}`;
          if (urlSessionId !== sid) goto(path);
        }
      },
      failAssistant,
      options,
    );
  }

  // --- Feature 8: Edit / Regenerate ---
  function handleSendMessage(text: string, slashCommand?: string) {
    const userMsg: ChatMessageType = {
      id: crypto.randomUUID(),
      session_id: sessionId || '',
      role: 'user',
      content: text,
    };
    messages.update((m) => [...m, userMsg]);
    startStreaming(text, slashCommand);
  }

  function handleEditMessage(messageId: string, newContent: string) {
    // Remove everything from this message onward, then resend
    messages.update((m) => {
      const idx = m.findIndex((msg) => msg.id === messageId);
      if (idx === -1) return m;
      return m.slice(0, idx);
    });
    // Send as if fresh — backend regenerates
    const userMsg: ChatMessageType = {
      id: crypto.randomUUID(),
      session_id: sessionId || '',
      role: 'user',
      content: newContent,
    };
    messages.update((m) => [...m, userMsg]);
    startStreaming(newContent);
  }

  function handleRegenerate(messageId: string) {
    // Find the message, remove it and everything after it
    let userText = '';
    messages.update((m) => {
      const idx = m.findIndex((msg) => msg.id === messageId);
      if (idx === -1) return m;
      const msg = m[idx];
      // If it's a user message, we need its content to resend
      if (msg.role === 'user') {
        userText = msg.content;
      } else {
        // Assistant message: find the preceding user message
        for (let i = idx - 1; i >= 0; i--) {
          if (m[i].role === 'user') {
            userText = m[i].content;
            break;
          }
        }
      }
      return m.slice(0, idx);
    });
    if (!userText) {
      toasts.add('Cannot regenerate: no user message found', 'error');
      return;
    }
    // Resend with regenerate flag
    streaming.set(true);

    const assistantMsg: ChatMessageType = {
      id: crypto.randomUUID(),
      session_id: sessionId || '',
      role: 'assistant',
      content: '',
    };
    messages.update((m) => [...m, assistantMsg]);
    const assistantId = assistantMsg.id;

    const docIds = selectedDocIds.size > 0 ? [...selectedDocIds] : undefined;

    abortFn = streamChat(
      sessionId || undefined,
      userText,
      projectId,
      docIds,
      (chunk) => {
        if (chunk == null) return;
        messages.update((m) => {
          const last = m[m.length - 1];
          if (last && last.id === assistantId) {
            last.content += chunk;
          }
          return m;
        });
      },
      (sources: SourceChunk[]) => {
        messages.update((m) => {
          const last = m[m.length - 1];
          if (last && last.id === assistantId) {
            last.sources = sources;
          }
          return m;
        });
      },
      (sid) => {
        streaming.set(false);
        abortFn = null;
        if (sid) {
          if (!sessionId) sessionId = sid;
          const path = projectId ? `/projects/${projectId}/chat/${sid}` : `/chat/${sid}`;
          if (urlSessionId !== sid) goto(path);
        }
      },
      failAssistant,
      { regenerate: true },
    );
  }

  // --- Feature 10: Error retry ---
  function handleRetry() {
    // Find the last user message, then strip the error and resend
    let userText = '';
    messages.update((m) => {
      for (let i = m.length - 1; i >= 0; i--) {
        if (m[i].role === 'user') {
          userText = m[i].content;
          break;
        }
      }
      // Remove the error assistant message
      if (m.length > 0 && m[m.length - 1].role === 'assistant') {
        m.pop();
      }
      return m;
    });
    if (userText) startStreaming(userText);
  }

  function toggleDoc(docId: string) {
    const next = new Set(selectedDocIds);
    if (next.has(docId)) next.delete(docId);
    else next.add(docId);
    selectedDocIds = next;
  }

  function clearDocs() {
    selectedDocIds = new Set();
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
      <ChatMessage
        message={msg}
        onEdit={handleEditMessage}
        onRegenerate={handleRegenerate}
        onRetry={!$streaming ? handleRetry : undefined}
      />
    {/each}
    {#if $messages.length === 0}
      <div class="flex h-full items-center justify-center text-slate-400">
        Ask a question about your documents to get started.
      </div>
    {/if}
  </div>

  <ChatInput
    onsend={handleSendMessage}
    onStop={stopStreaming}
    disabled={false}
    isStreaming={$streaming}
    {projectId}
    availableDocs={availableDocs}
    selectedDocIds={selectedDocIds}
    onToggleDoc={toggleDoc}
    onClearDocs={clearDocs}
  />
</div>
