<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { currentUser, token } from '$lib/features/auth/store';
  import { logout } from '$lib/features/auth/api';
  import { listSessions, deleteSession } from '$lib/features/chat/api';
  import { getProject } from '$lib/features/projects/api';
  import type { ChatSession } from '$lib/features/chat/types';
  import type { Project } from '$lib/features/projects/types';

  const globalLinks = [
    { href: '/projects', label: 'Projects', icon: '📁' },
    { href: '/graph', label: 'Graph', icon: '🕸️' },
    { href: '/skills', label: 'Skills', icon: '🧠' },
    { href: '/settings', label: 'Settings', icon: '⚙️' },
  ];

  let sessions = $state<ChatSession[]>([]);
  let project = $state<Project | null>(null);

  const projectId = $derived.by(() => {
    const m = /^\/projects\/([^/]+)/.exec($page.url.pathname);
    return m ? m[1] : null;
  });

  const inProject = $derived(projectId !== null);

  const projectLinks = $derived.by(() => {
    if (!projectId) return [];
    return [
      { href: `/projects/${projectId}/library`, label: 'Library', icon: '📚' },
      { href: `/projects/${projectId}/search`, label: 'Search', icon: '🔍' },
      { href: `/projects/${projectId}/chat`, label: 'Chat', icon: '💬' },
    ];
  });

  const sessionsBase = $derived(projectId ? `/projects/${projectId}/chat` : '/chat');
  const inProjectChat = $derived(/^\/projects\/[^/]+\/chat/.test($page.url.pathname));

  function isProjectLinkActive(link: { href: string; label: string }) {
    if ($page.url.pathname.startsWith(link.href)) return true;
    if (link.label === 'Library' && $page.url.pathname === `/projects/${projectId}`) return true;
    return false;
  }

  $effect(() => {
    project = null;
    if (!projectId) return;
    getProject(projectId)
      .then((p) => (project = p))
      .catch(() => {});
  });

  async function refreshSessions() {
    if (!projectId) return;
    try {
      const res = await listSessions(projectId);
      sessions = res.sessions;
    } catch {
      sessions = [];
    }
  }

  $effect(() => {
    if (inProjectChat) {
      refreshSessions();
    }
  });

  async function newChat() {
    goto(sessionsBase);
  }

  async function removeSession(id: string) {
    await deleteSession(id);
    sessions = sessions.filter((s) => s.id !== id);
    if ($page.url.pathname.endsWith(id)) {
      goto(sessionsBase);
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
    <a href="/projects" class="text-lg font-bold text-indigo-600">Notebook AI</a>
  </div>

  <nav class="flex flex-col gap-1 p-2">
    {#each globalLinks as link}
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

    {#if inProject}
      <div class="mt-2 border-t border-slate-200 pt-2">
        <p class="truncate px-3 pb-1 text-xs font-semibold uppercase text-slate-400">
          {project?.name ?? 'Project'}
        </p>
        {#each projectLinks as link}
          <a
            href={link.href}
            class="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 {isProjectLinkActive(link)
              ? 'bg-indigo-50 text-indigo-700 font-medium'
              : ''}"
          >
            <span>{link.icon}</span>
            <span>{link.label}</span>
          </a>
        {/each}
        <a
          href="/projects"
          class="flex items-center gap-3 rounded-lg px-3 py-2 text-sm text-slate-400 hover:bg-slate-100 hover:text-slate-600"
        >
          <span>🗂️</span>
          <span>All Projects</span>
        </a>
      </div>
    {/if}
  </nav>

  {#if inProjectChat}
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
              href={`${sessionsBase}/${s.id}`}
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
