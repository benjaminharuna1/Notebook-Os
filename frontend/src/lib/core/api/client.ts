import { get } from 'svelte/store';
import { token } from '$lib/features/auth/store';

export const BASE_URL: string =
  (import.meta.env?.VITE_API_URL as string | undefined) || 'http://localhost:8000/api/v1';

interface FetchOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
}

async function request<T>(endpoint: string, options: FetchOptions = {}): Promise<T> {
  const { method = 'GET', body, headers = {} } = options;

  const authToken = get(token);
  const config: RequestInit = {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      ...headers,
    },
    credentials: 'include',
  };

  if (body && method !== 'GET') {
    config.body = JSON.stringify(body);
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, config);

  if (response.status === 401) {
    if (typeof window !== 'undefined') {
      window.location.href = '/auth/login';
    }
    throw new Error('Unauthorized');
  }

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(err.detail || `API error: ${response.status}`);
  }

  if (response.status === 204) return undefined as T;
  return response.json();
}

export function createSSEConnection(
  endpoint: string,
  body: unknown,
  onChunk: (data: string) => void,
  onDone: (sessionId: string) => void,
  onError: (error: Error) => void,
  onSources?: (sources: unknown) => void,
): () => void {
  const controller = new AbortController();
  const authToken = get(token);

  fetch(`${BASE_URL}${endpoint}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
    },
    body: JSON.stringify(body),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        const err = await response.json().catch(() => ({ detail: `Request failed: ${response.status}` }));
        throw new Error(err.detail || `Request failed: ${response.status}`);
      }
      if (!response.body) throw new Error('No response body');
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let finished = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6));
            if (data.type === 'chunk') onChunk(data.content);
            else if (data.type === 'sources') {
              onSources?.(data.sources);
            } else if (data.type === 'error') {
              finished = true;
              onError(new Error(data.detail || 'Generation failed'));
            } else if (data.type === 'done') {
              finished = true;
              onDone(data.session_id);
            }
          }
        }
      }

      // Flush any remaining buffer (last event may lack trailing newline)
      if (buffer.trim()) {
        for (const line of buffer.split('\n')) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6));
            if (data.type === 'chunk') onChunk(data.content);
            else if (data.type === 'sources') {
              onSources?.(data.sources);
            } else if (data.type === 'error') {
              finished = true;
              onError(new Error(data.detail || 'Generation failed'));
            } else if (data.type === 'done') {
              finished = true;
              onDone(data.session_id);
            }
          }
        }
      }

      if (!finished) {
        onError(new Error('Connection closed before the response completed'));
      }
    })
    .catch((err) => {
      if (err.name !== 'AbortError') onError(err);
    });

  return () => controller.abort();
}

export const api = {
  get: <T>(endpoint: string) => request<T>(endpoint),
  post: <T>(endpoint: string, body: unknown) => request<T>(endpoint, { method: 'POST', body }),
  put: <T>(endpoint: string, body: unknown) => request<T>(endpoint, { method: 'PUT', body }),
  patch: <T>(endpoint: string, body: unknown) => request<T>(endpoint, { method: 'PATCH', body }),
  delete: <T>(endpoint: string) => request<T>(endpoint, { method: 'DELETE' }),
};
