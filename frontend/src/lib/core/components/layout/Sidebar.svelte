<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { currentUser, token } from '$lib/features/auth/store';
  import { logout } from '$lib/features/auth/api';

  const links = [
    { href: '/chat', label: 'Chat', icon: '💬' },
    { href: '/library', label: 'Library', icon: '📚' },
    { href: '/search', label: 'Search', icon: '🔍' },
    { href: '/graph', label: 'Graph', icon: '🕸️' },
    { href: '/settings', label: 'Settings', icon: '⚙️' },
  ];

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

  <nav class="flex flex-1 flex-col gap-1 p-2">
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
