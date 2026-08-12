export interface Document {
  id: string;
  title: string;
  filename: string;
  file_type: string;
  file_size?: number;
  page_count?: number;
  status: string;
  created_at?: string;
  indexed_at?: string;
}

export interface DocumentList {
  documents: Document[];
  total: number;
  page: number;
}
