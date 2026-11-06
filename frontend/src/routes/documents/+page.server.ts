import { redirect } from '@sveltejs/kit';

// `/evidence` owns the chunk browser; keep `/documents` as a safe alias.
export function load({ url }: { url: URL }) {
	const params = new URLSearchParams();
	for (const key of ['source_type', 'offset']) {
		const value = url.searchParams.get(key);
		if (value) params.set(key, value);
	}
	const query = params.toString();
	throw redirect(308, `/evidence${query ? `?${query}` : ''}`);
}
