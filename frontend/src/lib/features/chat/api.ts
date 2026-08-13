import { createSSEConnection, api } from '$lib/core/api/client';
import type { ChatSession, ChatMessage } from './types';

export function streamChat(
  sessionId: string | undefined,
  message: string,
  projectId: string | undefined,
  onChunk: (text: string) => void,
  onDone: (sessionId: string) => void,
  onError: (error: Error) => void,
): () => void {
  return createSSEConnection(
    '/chat',
    { session_id: sessionId, message, project_id: projectId },
    onChunk,
    onDone,
    onError,
  );
}

export async function listSessions(projectId?: string): Promise<{ sessions: ChatSession[] }> {
  const query = projectId ? `?project_id=${encodeURIComponent(projectId)}` : '';
  return api.get<{ sessions: ChatSession[] }>(`/chat/sessions${query}`);
}

export async function getSession(id: string): Promise<{ session: ChatSession; messages: ChatMessage[] }> {
  return api.get<{ session: ChatSession; messages: ChatMessage[] }>(`/chat/sessions/${id}`);
}

export async function deleteSession(id: string): Promise<{ success: boolean }> {
  return api.delete<{ success: boolean }>(`/chat/sessions/${id}`);
}
