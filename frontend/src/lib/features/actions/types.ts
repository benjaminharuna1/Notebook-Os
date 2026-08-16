export type ActionStatus = 'queued' | 'running' | 'paused' | 'done' | 'error';

export interface ActionInfo {
  id: string;
  user_id: string;
  project_id: string;
  kind: string;
  title: string;
  status: ActionStatus;
  progress: number;
  stage: string | null;
  error: string | null;
  created_at: string;
  checkpoint?: { id: string; nodes?: number; edges?: number } | null;
}
