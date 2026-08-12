export interface SearchResult {
  chunk_id: string;
  content: string;
  score: number;
  document_id: string;
  document_title: string;
  page_number: number;
}

export interface SearchResponse {
  results: SearchResult[];
}
