declare global {
  interface Window {
    __GRAPH_PERF__?: boolean;
  }
}

export function installPerfWatch(threshold = 100): void {
  if (typeof window === 'undefined' || window.__GRAPH_PERF__) return;
  window.__GRAPH_PERF__ = true;

  try {
    const obs = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        const att = (entry as PerformanceLongTaskTiming).attribution?.[0];
        console.warn(
          `[perf] LONG TASK ${Math.round(entry.duration)}ms @ +${Math.round(entry.startTime)}ms`,
          att
            ? { container: att.containerType, name: att.containerName, script: att.scriptingInvokerType }
            : 'window main thread',
        );
      }
    });
    obs.observe({ type: 'longtask', buffered: true });
  } catch (e) {
    console.warn('[perf] long task observer unavailable:', e);
  }
  console.info('[perf] long task observer installed (threshold ' + threshold + 'ms)');
}

export function timeOp(label: string, fn: () => void, threshold = 30): void {
  if (!window.__GRAPH_PERF__) return;
  const t0 = performance.now();
  fn();
  const ms = performance.now() - t0;
  if (ms >= threshold) console.warn(`[perf] ${label} took ${Math.round(ms)}ms`);
}
