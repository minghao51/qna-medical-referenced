import type { ApiErrorPayload, HealthResponse } from '$lib/types';

const LOCALHOST_NAMES = new Set(['localhost', '127.0.0.1']);

export function normalizeApiBase(value: string | null | undefined): string {
	const configured = (value ?? '').trim().replace(/\/+$/, '');
	if (!configured) return '';
	if (/^https?:\/\//i.test(configured) || configured.startsWith('/')) return configured;
	// Unsupported schemes and bare relative paths are not treated as an API origin.
	return '';
}

export function getApiBaseUrl(): string {
	const configured = normalizeApiBase(import.meta.env.VITE_API_URL);
	if (configured) return configured;

	if (typeof window === 'undefined') return '';

	if (LOCALHOST_NAMES.has(window.location.hostname)) return 'http://localhost:8000';

	return '';
}

/** Resolve a configured API base and path without assuming a browser origin exists. */
export function resolveApiUrl(base: string, path: string, origin: string): string {
	const normalized = normalizeApiBase(base);
	if (/^https?:\/\//i.test(normalized)) return `${normalized}${path}`;
	if (normalized.startsWith('/')) return `${origin}${normalized}${path}`;
	return `${origin}${path}`;
}

export async function parseApiError(response: Response): Promise<string> {
	let payload: ApiErrorPayload | null = null;
	try {
		payload = (await response.json()) as ApiErrorPayload;
	} catch {
		payload = null;
	}

	if (response.status === 429) {
		const retryAfter = response.headers.get('Retry-After');
		return retryAfter
			? `Rate limit exceeded. Retry in ${retryAfter}s.`
			: 'Rate limit exceeded. Please try again shortly.';
	}

	return payload?.detail || payload?.error?.code || `Request failed with status ${response.status}`;
}

let _baseUrl: string | null = null;

function baseUrl(): string {
	if (!_baseUrl) _baseUrl = getApiBaseUrl();
	return _baseUrl;
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
	const response = await fetch(`${baseUrl()}${path}`, {
		credentials: 'include',
		...init
	});
	if (!response.ok) {
		throw new Error(await parseApiError(response));
	}
	return (await response.json()) as T;
}

function apiUrl(path: string): string {
	return `${baseUrl()}${path}`;
}

export async function fetchHealthStatus(apiBaseUrl?: string): Promise<HealthResponse> {
	const base = apiBaseUrl || baseUrl();
	const response = await fetch(`${base}/health`, { credentials: 'include' });
	if (!response.ok) {
		throw new Error(await parseApiError(response));
	}
	return (await response.json()) as HealthResponse;
}

export async function getHistory(): Promise<{ history: unknown[] }> {
	return apiFetch<{ history: unknown[] }>('/history');
}

export async function clearHistory(): Promise<void> {
	const response = await fetch(`${baseUrl()}/history`, {
		method: 'DELETE',
		credentials: 'include'
	});
	if (!response.ok) {
		throw new Error(await parseApiError(response));
	}
}

export function chatStreamUrl(includePipeline: boolean): string {
	const origin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost';
	const url = new URL(resolveApiUrl(baseUrl(), '/chat', origin));
	if (includePipeline) url.searchParams.append('include_pipeline', 'true');
	return url.toString();
}

export function chatFetchRequest(message: string, url: string): RequestInit {
	return {
		method: 'POST',
		credentials: 'include',
		headers: {
			'Content-Type': 'application/json',
			Accept: 'text/event-stream'
		},
		body: JSON.stringify({ message })
	};
}

export async function getConfig<T>(): Promise<T> {
	return apiFetch<T>('/config');
}

export async function getDocuments<T>(params: {
	limit: number;
	offset: number;
	sourceType?: string;
}): Promise<T> {
	const qs = new URLSearchParams();
	qs.set('limit', String(params.limit));
	qs.set('offset', String(params.offset));
	if (params.sourceType) qs.set('source_type', params.sourceType);
	return apiFetch<T>(`/documents?${qs.toString()}`);
}

export async function getDocument<T>(docId: string): Promise<T> {
	return apiFetch<T>(`/documents/${encodeURIComponent(docId)}`);
}

export async function getLatestEvaluation<T>(): Promise<T> {
	return apiFetch<T>('/evaluation/latest');
}

export async function getEvaluationHistory<T>(limit: number = 20): Promise<T> {
	return apiFetch<T>(`/evaluation/history?limit=${limit}`);
}

export async function getEvaluationRun<T>(runDir: string): Promise<T> {
	return apiFetch<T>(`/evaluation/run/${encodeURIComponent(runDir)}`);
}

export async function getAblationResults<T>(): Promise<T> {
	return apiFetch<T>('/evaluation/ablation');
}

export async function getFullAblationResults<T>(): Promise<T> {
	return apiFetch<T>('/evaluation/ablation/full');
}

export async function getEvaluationRuns<T>(): Promise<T> {
	return apiFetch<T>('/evaluation/runs');
}

export async function getStepMetrics<T>(stage: string, runDir?: string): Promise<T> {
	const query = runDir ? `?run_dir=${encodeURIComponent(runDir)}` : '';
	return apiFetch<T>(`/evaluation/steps/${encodeURIComponent(stage)}${query}`);
}

export async function getStepRecords<T>(
	stage: string,
	limit: number = 100,
	runDir?: string
): Promise<T> {
	const params = new URLSearchParams({ limit: String(limit) });
	if (runDir) params.set('run_dir', runDir);
	return apiFetch<T>(
		`/evaluation/steps/${encodeURIComponent(stage)}/records?${params.toString()}`
	);
}

export async function getL6Records<T>(limit: number = 100, runDir?: string): Promise<T> {
	const params = new URLSearchParams({ limit: String(limit) });
	if (runDir) params.set('run_dir', runDir);
	return apiFetch<T>(`/evaluation/l6/records?${params.toString()}`);
}

export async function getAnswerQuality<T>(runDir: string): Promise<T> {
	return apiFetch<T>(`/evaluation/answer-quality/${encodeURIComponent(runDir)}`);
}

export async function getExperiments<T>(): Promise<T> {
	return apiFetch<T>('/experiments');
}

export async function getExperimentResults<T>(experimentName: string): Promise<T> {
	return apiFetch<T>(`/experiments/${encodeURIComponent(experimentName)}/results`);
}

export async function getExperimentConfig<T>(experimentName: string): Promise<T> {
	return apiFetch<T>(`/experiments/${encodeURIComponent(experimentName)}/config`);
}

export async function getResearchDatasets<T>(): Promise<T> {
	return apiFetch<T>('/research-data/datasets');
}

export async function getResearchDataset<T>(datasetId: string): Promise<T> {
	return apiFetch<T>(`/research-data/datasets/${encodeURIComponent(datasetId)}`);
}

export async function getResearchDatasetCases<T>(
	datasetId: string,
	params: { revision: string; limit?: number; offset?: number }
): Promise<T> {
	const query = new URLSearchParams({
		revision: params.revision,
		limit: String(params.limit ?? 20),
		offset: String(params.offset ?? 0)
	});
	return apiFetch<T>(
		`/research-data/datasets/${encodeURIComponent(datasetId)}/cases?${query.toString()}`
	);
}
