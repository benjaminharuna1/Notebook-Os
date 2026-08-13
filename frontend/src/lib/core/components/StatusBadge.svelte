<script lang="ts">
  let { status }: { status: string } = $props();

  interface BadgeConfig {
    label: string;
    icon: string;
    cls: string;
    spin?: boolean;
  }

  const configs: Record<string, BadgeConfig> = {
    queued: { label: 'Queued', icon: '⏳', cls: 'bg-slate-100 text-slate-600' },
    processing: { label: 'Processing', icon: '⏳', cls: 'bg-indigo-100 text-indigo-700', spin: true },
    paused: { label: 'Paused', icon: '⏸️', cls: 'bg-amber-100 text-amber-700' },
    indexed: { label: 'Ready', icon: '✅', cls: 'bg-emerald-100 text-emerald-700' },
    failed: { label: 'Failed', icon: '❌', cls: 'bg-red-100 text-red-700' },
    // legacy statuses
    pending: { label: 'Queued', icon: '⏳', cls: 'bg-slate-100 text-slate-600' },
    indexing: { label: 'Processing', icon: '⏳', cls: 'bg-indigo-100 text-indigo-700', spin: true },
    ready: { label: 'Ready', icon: '✅', cls: 'bg-emerald-100 text-emerald-700' },
    error: { label: 'Failed', icon: '❌', cls: 'bg-red-100 text-red-700' },
  };

  const cfg = $derived(configs[status] || { label: status, icon: '•', cls: 'bg-slate-100 text-slate-600' });
</script>

<span class="inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-xs font-medium {cfg.cls}">
  <span class:{animate-spin}="{cfg.spin}">{cfg.icon}</span>
  {cfg.label}
</span>
