<script lang="ts">
  import { uploadFile } from '../api';
  import { uploadQueue } from '../store';

  const MAX_SIZE_MB = 25;

  let dragging = $state(false);

  async function handleFiles(files: File[]) {
    for (const file of files) {
      const id = uploadQueue.add(file);
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        uploadQueue.markError(id, 'Only .pdf files are supported');
        continue;
      }
      if (file.size > MAX_SIZE_MB * 1024 * 1024) {
        uploadQueue.markError(id, `Max file size is ${MAX_SIZE_MB} MB`);
        continue;
      }
      try {
        await uploadFile(file);
        uploadQueue.markDone(id);
      } catch (err) {
        uploadQueue.markError(id, (err as Error).message);
      }
    }
  }

  function handleDragOver(e: DragEvent) {
    e.preventDefault();
    dragging = true;
  }

  function handleDragLeave() {
    dragging = false;
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault();
    dragging = false;
    handleFiles(Array.from(e.dataTransfer?.files || []));
  }

  function handleFileSelect(e: Event) {
    const input = e.target as HTMLInputElement;
    handleFiles(Array.from(input.files || []));
    input.value = '';
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
    <span class="text-sm text-slate-600">Drop PDFs here or click to upload (max {MAX_SIZE_MB} MB)</span>
    <input type="file" class="hidden" multiple accept=".pdf" onchange={handleFileSelect} />
  </label>
</div>
