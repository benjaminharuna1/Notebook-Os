<script lang="ts">
  import { marked } from 'marked';
  import type { ChatMessage, SourceChunk } from '../types';
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
  let copied = $state(false);
  let refsOpen = $state(false);

  const isUser = $derived(message.role === 'user');
  const isError = $derived(message.content.startsWith('\u26a0\ufe0f'));
  const isAssistant = $derived(message.role === 'assistant');

  const sources = $derived.by(() => {
    if (!message.sources) return [];
    if (Array.isArray(message.sources)) return message.sources;
    try { return JSON.parse(message.sources as string); } catch { return []; }
  });

  // Unique references in order of first appearance
  const references = $derived.by(() => {
    const seen = new Set<string>();
    const refs: { index: number; title: string; apa: string; page?: number }[] = [];
    for (const s of sources) {
      const key = s.title || s.chunk_id;
      if (seen.has(key)) continue;
      seen.add(key);
      refs.push({
        index: refs.length + 1,
        title: s.title,
        apa: s.apa_reference || s.title || 'Unknown source',
        page: s.page,
      });
    }
    return refs;
  });

  // Build citation map: "Surname, Year" → reference index
  const citationMap = $derived.by(() => {
    const map = new Map<string, number>();
    for (const ref of references) {
      const m = ref.apa.match(/^([A-Z][a-z\u00C0-\u024F]+(?:\s(?:de|da|von|van|di|el|al))?)/);
      const ym = ref.apa.match(/\((\d{4}[a-z]?)\)/);
      if (m && ym) {
        map.set(`${m[1]}, ${ym[1]}`.toLowerCase(), ref.index);
      }
    }
    return map;
  });

  const renderedContent = $derived.by(() => {
    if (!message.content || isUser) return '';
    let content = message.content;

    // Strip any auto-generated References section
    const refIdx = content.search(/^##\s*References?\s*$/im);
    if (refIdx !== -1) content = content.substring(0, refIdx).trimEnd();

    let html: string;
    try { html = marked.parse(content, { async: false }) as string; }
    catch { html = content; }

    if (references.length === 0) return html;

    const APA_TIP = 'citation-tip pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 hidden w-80 -translate-x-1/2 rounded-lg border border-slate-200 bg-white p-2.5 text-left text-[11px] leading-snug text-slate-600 shadow-lg group-hover/ctx:block';
    const APA_LINK = 'citation-link group/ctx relative cursor-pointer text-indigo-600 font-medium hover:underline';

    // 1. Linkify parenthetical: (Smith, 2024) or (Smith, 2024, p. 15)
    html = html.replace(/\(([^()]+?,\s*\d{4}[a-z]?(?:,\s*p\.\s*\d+)?)\)/g, (match, inner) => {
      const key = inner.trim().toLowerCase();
      const idx = citationMap.get(key);
      if (idx) {
        const ref = references[idx - 1];
        return `<span class="${APA_LINK}" data-ref="${idx}">${match}<span class="${APA_TIP}">${ref.apa.replace(/"/g, '&quot;')}</span></span>`;
      }
      return match;
    });

    // 2. Linkify narrative: "Smith (2020)" or "Smith and Jones (2019)" or "Smith et al. (2021)"
    html = html.replace(/([A-Z][a-z\u00C0-\u024F]+)\s+(?:and\s+[A-Z][a-z\u00C0-\u024F]+\s+)?(?:et al\.?\s*)?\((\d{4}[a-z]?)\)/g, (match, _author, year) => {
      // Try to find a reference matching this year
      const ref = references.find(r => {
        const ym = r.apa.match(/\((\d{4}[a-z]?)\)/);
        return ym && ym[1] === year;
      });
      if (ref) {
        return `<span class="${APA_LINK}" data-ref="${ref.index}">${match}<span class="${APA_TIP}">${ref.apa.replace(/"/g, '&quot;')}</span></span>`;
      }
      return match;
    });

    return html;
  });

  const copyContent = $derived.by(() => {
    if (!message.content) return '';
    let text = message.content;
    const refIdx = text.search(/^##\s*References?\s*$/im);
    if (refIdx !== -1) text = text.substring(0, refIdx).trimEnd();
    return text;
  });

  function startEdit() { editing = true; editText = message.content; }
  function confirmEdit() { if (!editText.trim()) return; editing = false; onEdit?.(message.id, editText.trim()); }
  function cancelEdit() { editing = false; editText = ''; }

  async function handleCopy() {
    try { await navigator.clipboard.writeText(copyContent); }
    catch {
      const ta = document.createElement('textarea');
      ta.value = copyContent;
      document.body.appendChild(ta); ta.select(); document.execCommand('copy');
      document.body.removeChild(ta);
    }
    copied = true;
    setTimeout(() => (copied = false), 2000);
  }

  function scrollToRef(refIdx: number) {
    const el = document.getElementById(`ref-${refIdx}`);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' });
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
            if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); confirmEdit(); }
            if (e.key === 'Escape') cancelEdit();
          }}
        ></textarea>
        <div class="mt-1 flex justify-end gap-2">
          <button onclick={cancelEdit} class="rounded px-2 py-0.5 text-xs text-slate-500 hover:text-slate-700">Cancel</button>
          <button onclick={confirmEdit} class="rounded bg-indigo-600 px-2 py-0.5 text-xs font-medium text-white hover:bg-indigo-700">Save &amp; Send</button>
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

    <!-- Model indicator + Copy -->
    {#if isAssistant && !editing}
      <div class="mt-1 flex items-center gap-2 pl-1">
        {#if message.model_used}
          <span class="text-[10px] text-slate-400">{message.model_used}</span>
        {/if}
        {#if message.content}
          <button onclick={handleCopy} class="flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] text-slate-400 hover:bg-slate-100 hover:text-slate-600" title="Copy response">
            {#if copied}
              <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3 text-green-500" viewBox="0 0 20 20" fill="currentColor"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd" /></svg>
              Copied
            {:else}
              <svg xmlns="http://www.w3.org/2000/svg" class="h-3 w-3" viewBox="0 0 20 20" fill="currentColor"><path d="M8 3a1 1 0 011-1h2a1 1 0 110 2H9a1 1 0 01-1-1z" /><path d="M6 3a2 2 0 00-2 2v11a2 2 0 002 2h8a2 2 0 002-2V5a2 2 0 00-2-2 3 3 0 01-3 3H9a3 3 0 01-3-3z" /></svg>
              Copy
            {/if}
          </button>
        {/if}
      </div>
    {/if}

    <!-- Hover actions -->
    {#if !editing && message.content}
      <div class="absolute -top-8 right-0 hidden group-hover:flex gap-1">
        {#if isUser}
          <button onclick={startEdit} class="rounded-lg border border-slate-200 bg-white px-2 py-1 text-[10px] text-slate-500 shadow-sm hover:bg-slate-50">Edit</button>
          <button onclick={() => onRegenerate?.(message.id)} class="rounded-lg border border-slate-200 bg-white px-2 py-1 text-[10px] text-slate-500 shadow-sm hover:bg-slate-50">Resend</button>
        {:else if isAssistant && !isError}
          <button onclick={() => onRegenerate?.(message.id)} class="rounded-lg border border-slate-200 bg-white px-2 py-1 text-[10px] text-slate-500 shadow-sm hover:bg-slate-50">Regenerate</button>
        {/if}
      </div>
    {/if}

    {#if isError && onRetry}
      <div class="mt-2">
        <button onclick={onRetry} class="rounded-lg border border-red-200 bg-white px-3 py-1 text-xs font-medium text-red-600 hover:bg-red-50">Retry</button>
      </div>
    {/if}
  </div>
</div>

<!-- References dropdown -->
{#if !isUser && references.length > 0}
  <div class="mt-1.5 pl-1">
    <button
      onclick={() => (refsOpen = !refsOpen)}
      class="flex items-center gap-1.5 rounded-lg px-2 py-1 text-[11px] font-medium text-slate-500 hover:bg-slate-100"
    >
      <span>References ({references.length})</span>
      <span class="text-[9px] text-slate-400">{refsOpen ? '\u25B2' : '\u25BC'}</span>
    </button>
    {#if refsOpen}
      <div class="ml-1 mt-1 max-h-64 overflow-y-auto rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
        <ol class="list-inside space-y-2">
          {#each references as ref}
            <li id="ref-{ref.index}" class="scroll-mt-20 text-xs leading-relaxed text-slate-600">
              <span class="mr-1.5 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded bg-indigo-50 text-[9px] font-bold text-indigo-600">{ref.index}</span>
              <span class="text-slate-700">{ref.apa}</span>
            </li>
          {/each}
        </ol>
      </div>
    {/if}
  </div>
{/if}
