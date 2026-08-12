import { api } from '$lib/core/api/client';
import type { SearchResponse } from './types';

export async function search(query: string, topK: number = 5): Promise<SearchResponse> {
  return api.post<SearchResponse>('/search', { query, top_k: topK });
}
