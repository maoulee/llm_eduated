import { ref } from 'vue';
import { api } from '../api/client';

export interface ArtifactOptions {
  runId: string;
  type: 'outline' | 'final' | 'review' | 'solution' | 'revision_report' | 'manifest';
  slotId?: string;
}

export function useArtifact() {
  const isLoading = ref(false);
  const error = ref<string | null>(null);
  const content = ref<string | null>(null);

  async function fetchArtifact(options: ArtifactOptions) {
    try {
      isLoading.value = true;
      error.value = null;
      content.value = await api.getArtifact(options.runId, options.type, options.slotId);
      return content.value;
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch artifact';
      throw err;
    } finally {
      isLoading.value = false;
    }
  }

  function downloadArtifact(filename: string, content: string) {
    const blob = new Blob([content], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  return {
    isLoading,
    error,
    content,
    fetchArtifact,
    downloadArtifact,
  };
}
