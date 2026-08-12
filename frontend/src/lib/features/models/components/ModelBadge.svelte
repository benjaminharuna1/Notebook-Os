<script lang="ts">
  import { activeModel } from '../store';
</script>

{#if $activeModel}
  <span class="rounded-full bg-indigo-100 px-3 py-1 text-xs font-medium text-indigo-700">
    {$activeModel.name}
  </span>
{/if}
