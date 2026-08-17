<script lang="ts">
  import { marked } from 'marked';
  import type { ChatMessage } from '../types';
  import Spinner from '$lib/core/components/ui/Spinner.svelte';

  let {
    message,
    onEdit,
    onRegenerate,
    onRetry,
  }: {
    message: ChatMessage;
    onEdit?: (messageId: string, newContent: string) => void;
    onRegenerate?: (messageId: string) => void;
    onRetry?: () => void;
  } = $props();

  let editing = $state(false);
  let editText = $state('');

  const isUser = $derived(message.role === 'user');
  const isError = $derived(message.content.startsWith('⚠️'));
  const isAssistant = $derived(message.role === 'assistant');

  const renderedContent = $derived.by(() => {
    if (!message.content) return '';
    if (isUser) return '';
    try {
      return marked.parse(message.content, { async: false }) as string;
    } catch {
      return message.content;
    }
  });

  const sources = $derived.by(() => {
    if (!message.sources) return [];
    if (Array.isArray(message.sources)) return message.sources;
    try {
      return JSON.parse(message.sources as string);
    } catch {
      return [];
    }
  });

  function startEdit() {
    editing = true;
    editText = message.content;
  }

  function confirmEdit() {
    if (!editText.trim()) return;
    editing = false;
    onEdit?.(message.id, editText.trim());
  }

  function cancelEdit() {
    editing = false;
    editText = '';
  }
</script>

<div class="group flex {isUser ? 'justify-end' : 'justify-start'}">
  <div class="relative max-w-[80%]">
    <div
      class="rounded-2xl px-4 py-3 {isUser
        ? 'bg-indigo-600 text-white'
        : isError
          ? 'bg-red-50 text-red-800'
          : 'bg-slate-100 text-slate-900'}"
    >
      {#if editing}
        <textarea
          bind:value={editText}
          rows="3"
          class="w-full rounded-lg border border-indigo-300 bg-white p-2 text-sm text-slate-900 outline-none focus:border-indigo-500"
          onkeydown={(e) => {
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
              e.preventDefault();
              confirmEdit();
            }
            if (e.key === 'Escape') cancelEdit();
          }}
        ></textarea>
        <div class="mt-1 flex justify-end gap-2">
          <button
            onclick={cancelEdit}
            class="rounded px-2 py-0.5 text-xs text-slate-500 hover:text-slate-700"
          >
            Cancel
          </button>
          <button
            onclick={confirmEdit}
            class="rounded bg-indigo-600 px-2 py-0.5 text-xs font-medium text-white hover:bg-indigo-700"
          >
            Save &amp; Send
          </button>
        </div>
      {:else if isUser}
        <p class="text-sm whitespace-pre-wrap">{message.content}</p>
      {:else}
        <div class="prose prose-sm prose-slate max-w-none prose-headings:mt-3 prose-headings:mb-1.5 prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 prose-pre:bg-slate-800 prose-pre:text-slate-100 prose-code:text-indigo-600 prose-code:before:content-none prose-code:after:content-none prose-strong:text-slate-900 prose-table:text-xs prose-th:px-2 prose-th:py-1 prose-td:px-2 prose-td:py-1 prose-th:border prose-td:border prose-th:border-slate-200 prose-td:border-slate-200">
          {@html renderedContent}
        </div>
      {/if}
      {#if !message.content && isAssistant}
        <Spinner size="sm" />
      {/if}
    </div>

    <!-- Model indicator -->
    {#if isAssistant && message.model_used && !editing}
      <div class="mt-1 flex items-center gap-1 pl-1">
        <span class="text-[10px] text-slate-400">{message.model_used}</span>
      </div>
    {/if}

    <!-- Action buttons on hover -->
    {#if !editing && message.content}
      <div class="absolute -top-8 right-0 hidden group-hover:flex gap-1">
        {#if isUser}
          <button
            onclick={startEdit}
            class="rounded-lg border border-slate-200 bg-white px-2 py-1 text-[10px] text-slate-500 shadow-sm hover:bg-slate-50"
          >
            ✏️ Edit
          </button>
          <button
            onclick={() => onRegenerate?.(message.id)}
            class="rounded-lg border border-slate-200 bg-white px-2 py-1 text-[10px] text-slate-500 shadow-sm hover:bg-slate-50"
          >
            🔄 Resend
          </button>
        {:else if isAssistant && !isError}
          <button
            onclick={() => onRegenerate?.(message.id)}
            class="rounded-lg border border-slate-200 bg-white px-2 py-1 text-[10px] text-slate-500 shadow-sm hover:bg-slate-50"
          >
            🔄 Regenerate
          </button>
        {/if}
      </div>
    {/if}

    <!-- Error retry button -->
    {#if isError && onRetry}
      <div class="mt-2">
        <button
          onclick={onRetry}
          class="rounded-lg border border-red-200 bg-white px-3 py-1 text-xs font-medium text-red-600 hover:bg-red-50"
        >
          ↻ Retry
        </button>
      </div>
    {/if}
  </div>
</div>

{#if !isUser && sources.length > 0}
  <div class="flex {isUser ? 'justify-end' : 'justify-start'}">
    <div class="flex max-w-[80%] flex-wrap gap-1.5 pl-1">
      {#each sources as source}
        <span class="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] text-slate-500">
          <span>📄</span>
          <span class="font-medium">{source.title}</span>
          {#if source.page}
            <span>, p. {source.page}</span>
          {/if}
        </span>
      {/each}
    </div>
  </div>
{/if}
