<script lang="ts">
  import { goto } from '$app/navigation';
  import { login } from '$lib/features/auth/api';
  import { currentUser, token } from '$lib/features/auth/store';
  import PasswordInput from '$lib/core/components/ui/PasswordInput.svelte';

  let email = $state('');
  let password = $state('');
  let error = $state('');
  let loading = $state(false);

  async function handleLogin() {
    if (!email || !password) return;
    loading = true;
    error = '';
    try {
      const res = await login(email, password);
      token.set(res.token);
      currentUser.set(res.user);
      goto('/projects');
    } catch (e) {
      error = (e as Error).message;
    } finally {
      loading = false;
    }
  }
</script>

<div class="flex min-h-screen items-center justify-center bg-slate-50">
  <div class="w-full max-w-sm rounded-xl bg-white p-8 shadow-sm">
    <h1 class="mb-6 text-2xl font-bold text-slate-900">Sign In</h1>

    {#if error}
      <div class="mb-4 rounded-lg bg-red-50 px-4 py-2 text-sm text-red-600">{error}</div>
    {/if}

    <form onsubmit={(e) => { e.preventDefault(); handleLogin(); }} class="space-y-4">
      <div>
        <label for="email" class="mb-1 block text-sm font-medium text-slate-700">Email</label>
        <input
          id="email"
          type="email"
          bind:value={email}
          class="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm outline-none focus:border-indigo-500"
          required
        />
      </div>
      <div>
        <label for="password" class="mb-1 block text-sm font-medium text-slate-700">Password</label>
        <PasswordInput
          id="password"
          bind:value={password}
          placeholder="Password"
          required
          class="px-4 py-2 focus:border-indigo-500"
        />
      </div>
      <button
        type="submit"
        disabled={loading}
        class="w-full rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
      >
        {loading ? 'Signing in...' : 'Sign In'}
      </button>
    </form>

    <p class="mt-4 text-center text-sm text-slate-500">
      Don't have an account?
      <a href="/auth/register" class="text-indigo-600 hover:underline">Sign up</a>
    </p>
  </div>
</div>
