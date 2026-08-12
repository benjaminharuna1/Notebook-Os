import { writable } from 'svelte/store';
import type { User } from './types';
import { browser } from '$app/environment';

export const currentUser = writable<User | null>(null);
export const token = writable<string | null>(browser ? localStorage.getItem('token') : null);
export const isAuthenticated = writable<boolean>(false);

token.subscribe((val) => {
  if (browser) {
    if (val) {
      localStorage.setItem('token', val);
      isAuthenticated.set(true);
    } else {
      localStorage.removeItem('token');
      isAuthenticated.set(false);
    }
  }
});
