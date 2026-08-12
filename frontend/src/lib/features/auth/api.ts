import { api } from '$lib/core/api/client';
import type { AuthResponse, User } from './types';

export async function register(email: string, username: string, password: string): Promise<AuthResponse> {
  return api.post<AuthResponse>('/auth/register', { email, username, password });
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  return api.post<AuthResponse>('/auth/login', { email, password });
}

export async function logout(): Promise<void> {
  await api.post<void>('/auth/logout', {});
}

export async function getMe(): Promise<User> {
  return api.get<User>('/auth/me');
}
