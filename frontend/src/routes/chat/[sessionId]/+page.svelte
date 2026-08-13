<script lang="ts">
  import { page } from '$app/stores';
  import Header from '$lib/core/components/layout/Header.svelte';
  import ChatWindow from '$lib/features/chat/components/ChatWindow.svelte';

  let sessionId = $derived($page.params.sessionId);
</script>

<div class="flex h-full flex-col">
  <Header />
  <ChatWindow sessionId={sessionId} />
</div>
