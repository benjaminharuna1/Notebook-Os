export const CLUSTER_COLORS = [
  '#818cf8',
  '#34d399',
  '#f472b6',
  '#fbbf24',
  '#38bdf8',
  '#a78bfa',
  '#fb923c',
  '#4ade80',
];

export function clusterColor(id: string | null | undefined): string {
  const key = String(id ?? '');
  let hash = 0;
  for (let i = 0; i < key.length; i++) hash = (hash * 31 + key.charCodeAt(i)) >>> 0;
  return CLUSTER_COLORS[hash % CLUSTER_COLORS.length];
}
