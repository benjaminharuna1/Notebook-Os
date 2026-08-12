<script lang="ts">
  let { class: className = '', variant = 'primary', disabled = false, onclick, children }: {
    class?: string;
    variant?: 'primary' | 'secondary' | 'ghost';
    disabled?: boolean;
    onclick?: () => void;
    children?: import('svelte').Snippet;
  } = $props();
</script>

<button
  {onclick}
  {disabled}
  class="inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none {variant === 'primary'
    ? 'bg-indigo-600 text-white hover:bg-indigo-700'
    : variant === 'secondary'
      ? 'bg-slate-100 text-slate-900 hover:bg-slate-200'
      : 'text-slate-600 hover:bg-slate-100'} {className}"
>
  {@render children?.()}
</button>
