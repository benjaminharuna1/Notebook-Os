<script lang="ts">
  import Header from '$lib/core/components/layout/Header.svelte';
  import ChatWindow from '$lib/features/chat/components/ChatWindow.svelte';
  import FileDropzone from '$lib/features/ingestion/components/FileDropzone.svelte';
  import UploadQueue from '$lib/features/ingestion/components/UploadQueue.svelte';
</script>

<div class="flex h-full flex-col">
  <Header />
  <div class="flex flex-1">
    <div class="flex flex-1 flex-col">
      <ChatWindow />
    </div>
    <div class="w-80 border-l border-slate-200 p-4 space-y-4">
      <FileDropzone />
      <UploadQueue />
    </div>
  </div>
</div>
