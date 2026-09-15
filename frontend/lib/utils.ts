import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';
export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)); }

export async function api<T>(path: string, data?: unknown): Promise<T> {
  const response = await fetch(`/api/${path}`, {
    method: data === undefined ? 'GET' : 'POST',
    headers: data === undefined ? undefined : {'content-type': 'application/json'},
    body: data === undefined ? undefined : JSON.stringify(data), cache: 'no-store',
  });
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || 'Please try again.');
  return result;
}

/** Await durable work while retaining the existing progress/error UI. */
export async function aiTask<T>(path: string, data: unknown, signal?: AbortSignal): Promise<T> {
  let jobId: string | undefined;
  const cancel = () => {
    if (jobId) void fetch(`/api/jobs/${jobId}/cancel`, {method: 'POST', keepalive: true}).catch(() => {});
  };
  signal?.addEventListener('abort', cancel, {once: true});
  try {
    // Let initial submission finish so a cancellation can also cancel its newly allocated job.
    const response = await fetch(`/api/${path}`, {
      method: 'POST', headers: {...(data instanceof FormData ? {} : {'content-type': 'application/json'}), 'Idempotency-Key': crypto.randomUUID()},
      body: data instanceof FormData ? data : JSON.stringify(data), cache: 'no-store',
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Please try again.');
    if (response.status !== 202) return result;
    jobId = result.jobId;
    if (!jobId) throw new Error('The task could not start. Please retry.');
    if (signal?.aborted) { cancel(); throw new DOMException('Cancelled', 'AbortError'); }
    const deadline = Date.now() + 15 * 60 * 1000;
    while (Date.now() < deadline) {
      signal?.throwIfAborted();
      const poll = await fetch(`/api/jobs/${jobId}`, {signal, cache: 'no-store'});
      const job = await poll.json();
      if (!poll.ok) throw new Error(job.error || 'Please try again.');
      if (job.status === 'completed') return job.result;
      if (job.status === 'failed' || job.status === 'cancelled') throw new Error(job.error || 'Please retry.');
      await new Promise<void>((resolve, reject) => {
        const onAbort = () => { clearTimeout(timer); reject(new DOMException('Cancelled', 'AbortError')); };
        const timer = setTimeout(() => { signal?.removeEventListener('abort', onAbort); resolve(); }, 1500);
        signal?.addEventListener('abort', onAbort, {once: true});
      });
    }
    cancel();
    throw new Error('This task is taking too long. Please try again.');
  } finally {
    signal?.removeEventListener('abort', cancel);
  }
}
