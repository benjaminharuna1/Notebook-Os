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
  let docPickerOpen = $state(false);
  let availableDocs = $state<{ id: string; title: string }[]>([]);
  let docSearch = $state('');

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
    messages.update((m) => {
      const last = m[m.length - 1];
      if (last && last.role === 'assistant') {
        last.content = `⚠️ ${error.message}`;
      }
      return m;
    });
    toasts.add(error.message, 'error');
  }

  function stopStreaming() {
    abortFn?.();
    streaming.set(false);
    abortFn = null;
    toasts.add('Generation stopped.', 'info');
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
    const assistantId = assistantMsg.id;

    const docIds = selectedDocIds.size > 0 ? [...selectedDocIds] : undefined;

    abortFn = streamChat(
      sessionId || undefined,
      text,
      projectId,
      docIds,
      (chunk) => {
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
    );
  }

  function scrollToBottom(node: HTMLDivElement) {
    $effect(() => {
      if ($messages.length) {
        node.scrollTop = node.scrollHeight;
      }
    });
  }

  const filteredDocs = $derived(
    docSearch
      ? availableDocs.filter((d) => d.title.toLowerCase().includes(docSearch.toLowerCase()))
      : availableDocs
  );
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

  {#if availableDocs.length > 0}
    <div class="border-t border-slate-100 px-6 pt-3">
      <div class="flex items-center gap-2">
        <button
          onclick={() => (docPickerOpen = !docPickerOpen)}
          class="flex items-center gap-1.5 rounded-lg border border-slate-200 px-2.5 py-1 text-[11px] font-medium text-slate-500 hover:bg-slate-50"
        >
          <span>📄</span>
          <span>
            {selectedDocIds.size === 0
              ? 'All papers'
              : `${selectedDocIds.size} paper${selectedDocIds.size > 1 ? 's' : ''} selected`}
          </span>
          <span class="text-[10px]">{docPickerOpen ? '▲' : '▼'}</span>
        </button>
        {#if selectedDocIds.size > 0}
          <button
            onclick={() => (selectedDocIds = new Set())}
            class="text-[10px] text-slate-400 hover:text-slate-600"
          >
            Clear
          </button>
        {/if}
      </div>
      {#if docPickerOpen}
        <div class="mt-2 max-h-40 overflow-y-auto rounded-lg border border-slate-200 bg-white p-2 shadow-sm">
          <input
            bind:value={docSearch}
            placeholder="Search papers…"
            class="mb-1.5 w-full rounded border border-slate-200 px-2 py-1 text-xs outline-none focus:border-indigo-400"
          />
          {#each filteredDocs as doc}
            <label class="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-xs hover:bg-slate-50">
              <input
                type="checkbox"
                checked={selectedDocIds.has(doc.id)}
                onchange={() => {
                  const next = new Set(selectedDocIds);
                  if (next.has(doc.id)) next.delete(doc.id);
                  else next.add(doc.id);
                  selectedDocIds = next;
                }}
                class="h-3 w-3 accent-indigo-600"
              />
              <span class="truncate text-slate-700">{doc.title}</span>
            </label>
          {/each}
        </div>
      {/if}
    </div>
  {/if}

  <ChatInput onsend={sendMessage} onStop={stopStreaming} disabled={false} isStreaming={$streaming} />
</div>
