export const languages = { en: 'English', de: 'Deutsch', tr: 'Türkçe', ar: 'العربية', es: 'Español' } as const;
export type Language = keyof typeof languages;
export type SourceLanguage = Language | 'mixed' | 'und';
export interface Contribution { id: string; neighborhood_id: string; nickname: string; body: string; language: SourceLanguage; input_mode: 'text' | 'voice'; created_at: string; diary_date: string; demo_dataset: string | null; }
export interface Chronicle { id: string; neighborhood_id: string; diary_date: string; body: string; language: Language; title: string; source_ids: string[]; contribution_count: number; status: 'pending' | 'generating' | 'published' | 'failed' | 'review'; demo_dataset: string | null; }
export interface Neighborhood { id: string; name: string; district: string; aliases: string[]; description: string; color: string; center: [number, number]; geometry: { type: 'Polygon'; coordinates: number[][][] }; }
export interface KiezSummary { neighborhood: Neighborhood; latest: Contribution | null; count: number; archiveCount: number; }
