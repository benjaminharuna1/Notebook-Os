<script lang="ts">
  let { value = $bindable(''), placeholder = '', id = '', required = false, class: className = '' }: {
    value?: string;
    placeholder?: string;
    id?: string;
    required?: boolean;
    class?: string;
  } = $props();

  let visible = $state(false);
</script>

<div class="relative">
  <input
    {id}
    type={visible ? 'text' : 'password'}
    bind:value
    {placeholder}
    {required}
    class="w-full rounded-lg border border-slate-300 pr-10 text-sm outline-none focus:border-indigo-500 {className}"
  />
  <button
    type="button"
    onclick={() => (visible = !visible)}
    aria-label={visible ? 'Hide password' : 'Show password'}
    class="absolute inset-y-0 right-0 flex w-9 items-center justify-center text-slate-400 hover:text-slate-600"
  >
    {#if visible}
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M9.88 9.88a3 3 0 1 0 4.24 4.24" />
        <path d="M10.73 5.08A10.43 10.43 0 0 1 12 5c7 0 11 8 11 8a13.16 13.16 0 0 1-1.67 2.68" />
        <path d="M6.61 6.61A13.53 13.53 0 0 0 1 12s4 8 11 8a9.74 9.74 0 0 0 5.39-1.61" />
        <path d="m2 2 20 20" />
      </svg>
    {:else}
      <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8Z" />
        <circle cx="12" cy="12" r="3" />
      </svg>
    {/if}
  </button>
</div>
