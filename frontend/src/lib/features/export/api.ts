import { downloadFile } from '$lib/core/api/client';

export type ExportFormat = 'docx' | 'xlsx';

export function exportDossier(projectId: string, format: ExportFormat = 'docx'): Promise<string> {
  return downloadFile(`/projects/${projectId}/export/dossier?format=${format}`);
}

export function exportReferences(
  projectId: string,
  format: ExportFormat = 'docx',
): Promise<string> {
  return downloadFile(`/projects/${projectId}/export/references?format=${format}`);
}

export function exportConversation(projectId: string, sessionId: string): Promise<string> {
  return downloadFile(
    `/projects/${projectId}/export/conversation/${sessionId}?format=docx`,
  );
}
