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

export async function fetchHealthStatus(apiBaseUrl: string): Promise<HealthResponse> {
	const response = await fetch(`${apiBaseUrl}/health`, { credentials: 'include' });
	if (!response.ok) {
		throw new Error(await parseApiError(response));
	}
	return (await response.json()) as HealthResponse;
}
