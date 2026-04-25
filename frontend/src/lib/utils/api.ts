import type { ApiErrorPayload, HealthResponse } from '$lib/types';

const LOCALHOST_NAMES = new Set(['localhost', '127.0.0.1']);

export function getApiBaseUrl(): string {
	const configured = (import.meta.env.VITE_API_URL || '').trim();
	if (configured) {
		return configured.replace(/\/$/, '');
	}

	if (typeof window === 'undefined') {
		return '';
	}

	if (LOCALHOST_NAMES.has(window.location.hostname)) {
		return 'http://localhost:8000';
	}

	return '';
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
	const url = new URL(`${baseUrl()}/chat`);
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

export async function getStepMetrics<T>(stage: string): Promise<T> {
	return apiFetch<T>(`/evaluation/steps/${encodeURIComponent(stage)}`);
}

export async function getStepRecords<T>(
	stage: string,
	limit: number = 100
): Promise<T> {
	return apiFetch<T>(
		`/evaluation/steps/${encodeURIComponent(stage)}/records?limit=${limit}`
	);
}

export async function getL6Records<T>(limit: number = 100): Promise<T> {
	return apiFetch<T>(`/evaluation/l6/records?limit=${limit}`);
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
