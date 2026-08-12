import { writable } from 'svelte/store';
import type { ModelConfig } from './types';

export const availableModels = writable<ModelConfig[]>([]);
export const activeModel = writable<ModelConfig | null>(null);
