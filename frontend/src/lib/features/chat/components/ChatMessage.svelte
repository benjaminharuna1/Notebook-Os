<script lang="ts">
  import { marked } from 'marked';
  import type { ChatMessage } from '../types';
  import Spinner from '$lib/core/components/ui/Spinner.svelte';

  let { message }: { message: ChatMessage } = $props();

  const isUser = $derived(message.role === 'user');

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
</script>

<div class="flex {isUser ? 'justify-end' : 'justify-start'}">
  <div
    class="max-w-[80%] rounded-2xl px-4 py-3 {isUser
      ? 'bg-indigo-600 text-white'
      : 'bg-slate-100 text-slate-900'}"
  >
    {#if isUser}
      <p class="text-sm whitespace-pre-wrap">{message.content}</p>
    {:else}
      <div class="prose prose-sm prose-slate max-w-none prose-headings:mt-3 prose-headings:mb-1.5 prose-p:my-1 prose-ul:my-1 prose-ol:my-1 prose-li:my-0 prose-pre:bg-slate-800 prose-pre:text-slate-100 prose-code:text-indigo-600 prose-code:before:content-none prose-code:after:content-none prose-strong:text-slate-900 prose-table:text-xs prose-th:px-2 prose-th:py-1 prose-td:px-2 prose-td:py-1 prose-th:border prose-td:border prose-th:border-slate-200 prose-td:border-slate-200">
        {@html renderedContent}
      </div>
    {/if}
    {#if !message.content && message.role === 'assistant'}
      <Spinner size="sm" />
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
