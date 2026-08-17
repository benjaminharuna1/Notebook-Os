<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import ChatWindow from '$lib/features/chat/components/ChatWindow.svelte';
  import { listSessions } from '$lib/features/chat/api';

  const projectId = $derived($page.params.id);

  const url = new URL(window.location.href);
  const forceNew = url.searchParams.has('new');

  let loaded = $state(false);

  $effect(() => {
    if (!projectId || loaded) return;
    loaded = true;
    if (forceNew) return;
    listSessions(projectId).then(({ sessions }) => {
      if (sessions.length > 0) {
        const sorted = [...sessions].sort(
          (a, b) => new Date(b.updated_at || b.created_at || '').getTime() - new Date(a.updated_at || a.created_at || '').getTime()
        );
        goto(`/projects/${projectId}/chat/${sorted[0].id}`, { replaceState: true });
      }
    });
  });
</script>

{#if loaded}
  <ChatWindow {projectId} />
{/if}
