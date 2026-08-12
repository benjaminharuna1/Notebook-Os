<script lang="ts">
  import { uploadFile } from '../api';
  import { uploadQueue } from '../store';

  let dragging = $state(false);

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
    dragging = true;
  }

  function handleDragLeave() {
    dragging = false;
  }

  async function handleDrop(e: DragEvent) {
    e.preventDefault();
    dragging = false;
    const files = Array.from(e.dataTransfer?.files || []);
    for (const file of files) {
      const id = uploadQueue.add(file);
      try {
        await uploadFile(file);
        uploadQueue.markDone(id);
      } catch (err) {
        uploadQueue.markError(id, (err as Error).message);
      }
    }
  }

  async function handleFileSelect(e: Event) {
    const input = e.target as HTMLInputElement;
    const files = Array.from(input.files || []);
    for (const file of files) {
      const id = uploadQueue.add(file);
      try {
        await uploadFile(file);
        uploadQueue.markDone(id);
      } catch (err) {
        uploadQueue.markError(id, (err as Error).message);
      }
    }
  }
</script>

<div
  class="flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-8 transition-colors {dragging
    ? 'border-indigo-500 bg-indigo-50'
    : 'border-slate-300 hover:border-slate-400'}"
  ondragover={handleDragOver}
  ondragleave={handleDragLeave}
  ondrop={handleDrop}
  role="button"
  tabindex="0"
>
  <label class="cursor-pointer">
    <span class="text-sm text-slate-600">Drop files here or click to upload</span>
    <input type="file" class="hidden" multiple accept=".pdf,.docx,.txt" onchange={handleFileSelect} />
  </label>
</div>
