<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { currentUser, token } from '$lib/features/auth/store';
  import { logout } from '$lib/features/auth/api';
  import { listSessions, deleteSession } from '$lib/features/chat/api';
  import type { ChatSession } from '$lib/features/chat/types';

  const links = [
    { href: '/chat', label: 'Chat', icon: '💬' },
    { href: '/library', label: 'Library', icon: '📚' },
    { href: '/search', label: 'Search', icon: '🔍' },
    { href: '/graph', label: 'Graph', icon: '🕸️' },
    { href: '/skills', label: 'Skills', icon: '🧠' },
    { href: '/settings', label: 'Settings', icon: '⚙️' },
  ];

  let sessions = $state<ChatSession[]>([]);

  async function refreshSessions() {
    try {
      const res = await listSessions();
      sessions = res.sessions;
    } catch {
      sessions = [];
    }
  }

  $effect(() => {
    if ($page.url.pathname.startsWith('/chat')) {
      refreshSessions();
    }
  });

  async function newChat() {
    goto('/chat');
  }

  async function removeSession(id: string) {
    await deleteSession(id);
    sessions = sessions.filter((s) => s.id !== id);
    if ($page.url.pathname.endsWith(id)) {
      goto('/chat');
    }
  }

  async function handleLogout() {
    await logout();
    token.set(null);
    currentUser.set(null);
    goto('/auth/login');
  }
</script>

<aside class="flex w-56 flex-col border-r border-slate-200 bg-slate-50">
  <div class="flex items-center gap-2 border-b border-slate-200 px-4 py-4">
    <span class="text-lg font-bold text-indigo-600">Notebook AI</span>
  </div>

  <nav class="flex flex-col gap-1 p-2">
    {#each links as link}
      <a
        href={link.href}
        class="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 {$page.url.pathname.startsWith(link.href)
          ? 'bg-indigo-50 text-indigo-700 font-medium'
          : ''}"
      >
        <span>{link.icon}</span>
        <span>{link.label}</span>
      </a>
    {/each}
  </nav>

  {#if $page.url.pathname.startsWith('/chat')}
    <div class="flex items-center justify-between px-4 pt-2 pb-1">
      <span class="text-xs font-medium uppercase text-slate-400">Sessions</span>
      <button
        onclick={newChat}
        class="text-xs font-medium text-indigo-600 hover:text-indigo-800"
        title="New chat"
      >
        + New
      </button>
    </div>
    <div class="flex-1 overflow-y-auto px-2 pb-2">
      {#if sessions.length === 0}
        <p class="px-2 py-1 text-xs text-slate-400">No sessions yet.</p>
      {:else}
        {#each sessions as s (s.id)}
          <div class="group flex items-center">
            <a
              href={`/chat/${s.id}`}
              class="flex-1 truncate rounded-lg px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-100 {$page.url.pathname.endsWith(s.id)
                ? 'bg-indigo-50 text-indigo-700 font-medium'
                : ''}"
            >
              {s.title || 'Untitled'}
            </a>
            <button
              onclick={() => removeSession(s.id)}
              class="hidden px-1 text-xs text-slate-400 hover:text-red-500 group-hover:block"
              title="Delete session"
            >
              ✕
            </button>
          </div>
        {/each}
      {/if}
    </div>
  {:else}
    <div class="flex-1" />
  {/if}

  <div class="border-t border-slate-200 p-3">
    <div class="mb-2 px-2 text-xs text-slate-400">{$currentUser?.email}</div>
    <button
      onclick={handleLogout}
      class="w-full rounded-lg px-3 py-2 text-left text-sm text-slate-600 hover:bg-slate-100"
    >
      Sign Out
    </button>
  </div>
</aside>
