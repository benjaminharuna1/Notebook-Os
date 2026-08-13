<script lang="ts">
  import Header from '$lib/core/components/layout/Header.svelte';
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { listProjects, createProject, deleteProject } from '$lib/features/projects/api';
  import { toasts } from '$lib/core/stores/toasts';
  import type { Project } from '$lib/features/projects/types';

  let projects = $state<Project[]>([]);
  let loading = $state(true);
  let name = $state('');
  let description = $state('');
  let creating = $state(false);
  let error = $state('');

  async function load() {
    try {
      const res = await listProjects();
      projects = res.projects;
    } catch (err) {
      toasts.add((err as Error).message, 'error');
    } finally {
      loading = false;
    }
  }

  onMount(load);

  async function handleCreate() {
    error = '';
    if (!name.trim()) {
      error = 'Project name is required';
      return;
    }
    creating = true;
    try {
      const project = await createProject(name.trim(), description.trim());
      name = '';
      description = '';
      goto(`/projects/${project.id}`);
    } catch (err) {
      error = (err as Error).message;
    } finally {
      creating = false;
    }
  }

  async function handleDelete(project: Project) {
    if (!confirm(`Delete project "${project.name}" and all of its documents?`)) return;
    try {
      await deleteProject(project.id);
      projects = projects.filter((p) => p.id !== project.id);
      toasts.add(`Deleted "${project.name}"`, 'success');
    } catch (err) {
      toasts.add((err as Error).message, 'error');
    }
  }
</script>

<div class="flex h-full flex-col">
  <Header />
  <div class="flex-1 overflow-auto p-6">
    <h1 class="mb-6 text-2xl font-bold text-slate-900">Projects</h1>

    <div class="mb-8 rounded-lg border border-slate-200 p-5">
      <h2 class="mb-3 text-sm font-semibold text-slate-700">Create a new project</h2>
      <div class="flex flex-col gap-3">
        <input
          bind:value={name}
          placeholder="Project name (e.g. Thesis, Q3 Report)"
          class="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm outline-none focus:border-indigo-500"
        />
        <input
          bind:value={description}
          placeholder="Description (optional)"
          class="w-full rounded-lg border border-slate-300 px-4 py-2 text-sm outline-none focus:border-indigo-500"
        />
        {#if error}
          <p class="text-sm text-red-500">{error}</p>
        {/if}
        <div>
          <button
            onclick={handleCreate}
            disabled={creating}
            class="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            {creating ? 'Creating...' : 'Create Project'}
          </button>
        </div>
      </div>
    </div>

    {#if loading}
      <div class="text-center text-slate-400">Loading...</div>
    {:else if projects.length === 0}
      <div class="rounded-lg border border-dashed border-slate-300 p-8 text-center text-slate-400">
        No projects yet. Create one to organize your documents and chats.
      </div>
    {:else}
      <div class="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {#each projects as project (project.id)}
          <div class="flex flex-col rounded-lg border border-slate-200 p-4">
            <div class="min-w-0">
              <a href="/projects/{project.id}" class="text-lg font-semibold text-slate-900 hover:text-indigo-600">
                {project.name}
              </a>
              <p class="mt-1 text-sm text-slate-500">{project.description || 'No description'}</p>
            </div>
            <div class="mt-3 flex items-center justify-between border-t border-slate-100 pt-3 text-xs text-slate-400">
              <span>{project.doc_count} document{project.doc_count === 1 ? '' : 's'}</span>
              <div class="flex items-center gap-3">
                <a href="/projects/{project.id}" class="font-medium text-indigo-600 hover:text-indigo-800">
                  Open
                </a>
                <button onclick={() => handleDelete(project)} class="text-red-500 hover:text-red-700">
                  Delete
                </button>
              </div>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </div>
</div>
