import { writable } from 'svelte/store';
import { listActions, pauseActionRequest, resumeActionRequest } from './api';
import type { ActionInfo } from './types';

/**
 * Global store of the current user's background actions (literature map
 * builds, graph generations, ...). Polled from AppShell so actions keep
 * running and stay visible when navigating between pages.
 */
export const actions = writable<ActionInfo[]>([]);

let timer: ReturnType<typeof setInterval> | null = null;
let started = false;

export async function refreshActions(): Promise<void> {
  try {
    actions.set(await listActions());
  } catch {
    // keep the last known list; the next poll retries
  }
}

export function startActionPolling(interval = 1500): void {
  if (started) return;
  started = true;
  void refreshActions();
  timer = setInterval(() => void refreshActions(), interval);
}

export function stopActionPolling(): void {
  if (timer) {
    clearInterval(timer);
    timer = null;
  }
  started = false;
}

export async function pauseAction(id: string): Promise<void> {
  await pauseActionRequest(id);
  await refreshActions();
}

export async function resumeAction(id: string): Promise<void> {
  await resumeActionRequest(id);
  await refreshActions();
}
