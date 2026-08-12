<script lang="ts">
  let { size = 'md', class: className = '' }: { size?: 'sm' | 'md' | 'lg'; class?: string } = $props();

  const sizeMap = { sm: 'h-4 w-4', md: 'h-6 w-6', lg: 'h-8 w-8' };
</script>

<div
  class="animate-spin rounded-full border-2 border-slate-200 border-t-indigo-600 {sizeMap[size]} {className}"
/>
