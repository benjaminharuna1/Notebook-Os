<script lang="ts">
  import { onMount } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import '../app.css';
  import AppShell from '$lib/core/components/layout/AppShell.svelte';
  import { currentUser, isAuthenticated, token } from '$lib/features/auth/store';
  import { getMe } from '$lib/features/auth/api';

  let { children }: { children?: import('svelte').Snippet } = $props();
  let checking = $state(true);

  onMount(async () => {
    const stored = localStorage.getItem('token');
    if (stored) {
      token.set(stored);
      try {
        const user = await getMe();
        currentUser.set(user);
      } catch {
        token.set(null);
        currentUser.set(null);
      }
    }
    checking = false;
  });

  const isAuthPage = $derived($page.url.pathname.startsWith('/auth'));

  $effect(() => {
    if (!checking && !$isAuthenticated && !isAuthPage) {
      goto('/auth/login');
    }
  });
</script>

{#if checking}
  <div class="flex h-screen items-center justify-center bg-slate-50">
    <div class="text-slate-400">Loading...</div>
  </div>
{:else if $isAuthenticated || isAuthPage}
  {#if isAuthPage}
    {@render children?.()}
  {:else}
    <AppShell>
      {@render children?.()}
    </AppShell>
  {/if}
{/if}
