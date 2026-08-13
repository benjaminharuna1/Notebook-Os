import { writable } from 'svelte/store';

export type UploadStatus = 'queued' | 'processing' | 'paused' | 'done' | 'error';

export interface UploadItem {
  id: string;
  documentId?: string;
  name: string;
  progress: number;
  status: UploadStatus;
  error?: string;
}

function createUploadStore() {
  const { subscribe, update } = writable<UploadItem[]>([]);

  return {
    subscribe,
    add(file: File) {
      const id = crypto.randomUUID();
      update((items) => [...items, { id, name: file.name, progress: 0, status: 'queued' as const }]);
      return id;
    },
    patch(id: string, patch: Partial<UploadItem>) {
      update((items) => items.map((i) => (i.id === id ? { ...i, ...patch } : i)));
    },
    remove(id: string) {
      update((items) => items.filter((i) => i.id !== id));
    },
  };
}

export const uploadQueue = createUploadStore();
