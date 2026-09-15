import 'server-only';
import { notFound } from 'next/navigation';
import type { Chronicle, Contribution, KiezSummary, Neighborhood } from './types';

async function read<T>(path: string): Promise<T> {
  const response = await fetch(`${process.env.API_INTERNAL_URL || 'http://127.0.0.1:8000'}/api/${path}`, {
    cache: 'no-store', signal: AbortSignal.timeout(10000),
  });
  if (response.status === 404) notFound();
  if (!response.ok) throw new Error('The notes could not load.');
  return response.json();
}
export const summaries = () => read<KiezSummary[]>('neighborhoods');
export const getNeighborhood = (slug: string) => read<Neighborhood>(`neighborhoods/${encodeURIComponent(slug)}`);
export const latest = (slug: string) => read<Contribution | null>(`latest?kiez=${encodeURIComponent(slug)}`);
export const archive = (slug: string) => read<Chronicle[]>(`neighborhoods/${encodeURIComponent(slug)}/archive`);

export const featured = () => read<{neighborhood:Neighborhood;story:Chronicle}[]>('featured-chronicles');
