import { writable } from 'svelte/store';

export interface UploadItem {
  id: string;
  name: string;
  progress: number;
  status: 'pending' | 'uploading' | 'processing' | 'done' | 'error';
  error?: string;
}

function createUploadStore() {
  const { subscribe, update } = writable<UploadItem[]>([]);

  return {
    subscribe,
    add(file: File) {
      const id = crypto.randomUUID();
      update((items) => [...items, { id, name: file.name, progress: 0, status: 'pending' }]);
      return id;
    },
    updateProgress(id: string, progress: number) {
      update((items) =>
        items.map((i) => (i.id === id ? { ...i, progress, status: 'uploading' as const } : i)),
      );
    },
    markDone(id: string) {
      update((items) => items.map((i) => (i.id === id ? { ...i, progress: 100, status: 'done' as const } : i)));
    },
    markError(id: string, error: string) {
      update((items) => items.map((i) => (i.id === id ? { ...i, status: 'error' as const, error } : i)));
    },
    remove(id: string) {
      update((items) => items.filter((i) => i.id !== id));
    },
  };
}

export const uploadQueue = createUploadStore();
