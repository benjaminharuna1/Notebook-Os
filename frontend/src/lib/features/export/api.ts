import { downloadFile } from '$lib/core/api/client';

export function exportWorkbook(projectId: string): Promise<string> {
  return downloadFile(`/projects/${projectId}/export/workbook`);
}

export function exportDossier(projectId: string, includeAnswers = false): Promise<string> {
  const query = includeAnswers ? '?include_answers=true' : '';
  return downloadFile(`/projects/${projectId}/export/dossier${query}`);
}
