<script lang="ts">
  import { uploadFile } from '../api';
  import { uploadQueue } from '../store';

  let { projectId }: { projectId?: string } = $props();

  const MAX_SIZE_MB = 25;
  const MAX_FILES = 50;

  let dragging = $state(false);

  function sanitizeFilename(name: string): string {
    return name.replace(/[<>:"/\\|?*\x00-\x1f]/g, '_').replace(/\.{2,}/g, '.').trim();
  }

  function isPdf(file: File): boolean {
    const name = file.name.toLowerCase();
    return name.endsWith('.pdf');
  }

  async function handleFiles(files: File[]) {
    const pdfs = Array.from(files).filter(isPdf).slice(0, MAX_FILES);

    for (const file of pdfs) {
      const id = uploadQueue.add(file);
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        uploadQueue.patch(id, { status: 'error', error: 'Only .pdf files are supported' });
        continue;
      }
      if (file.size > MAX_SIZE_MB * 1024 * 1024) {
        uploadQueue.patch(id, { status: 'error', error: `Max file size is ${MAX_SIZE_MB} MB` });
        continue;
      }
      if (file.size === 0) {
        uploadQueue.patch(id, { status: 'error', error: 'File is empty' });
        continue;
      }
      try {
        const res = await uploadFile(file, projectId);
        uploadQueue.patch(id, { documentId: res.document_id, status: 'processing' });
      } catch (err) {
        uploadQueue.patch(id, { status: 'error', error: (err as Error).message });
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
    <input
      type="file"
      class="hidden"
      multiple
      accept=".pdf"
      onchange={handleFileSelect}
    />
  </label>
  <label class="mt-2 cursor-pointer">
    <span class="text-[11px] text-slate-400 underline decoration-slate-300 underline-offset-2 hover:text-slate-600">
      or upload a folder
    </span>
    <input
      type="file"
      class="hidden"
      webkitdirectory
      directory
      multiple
      onchange={handleFileSelect}
    />
  </label>
</div>
