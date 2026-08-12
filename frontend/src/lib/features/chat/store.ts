import { writable } from 'svelte/store';
import type { ChatMessage, ChatSession } from './types';

export const sessions = writable<ChatSession[]>([]);
export const currentSessionId = writable<string | null>(null);
export const messages = writable<ChatMessage[]>([]);
export const streaming = writable(false);
