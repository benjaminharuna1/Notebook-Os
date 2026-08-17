<script lang="ts">
  import { page } from '$app/stores';
  import ChatWindow from '$lib/features/chat/components/ChatWindow.svelte';

  const projectId = $derived($page.params.id);
  const sessionId = $derived($page.params.sessionId);
</script>

<ChatWindow sessionId={sessionId} {projectId} />
