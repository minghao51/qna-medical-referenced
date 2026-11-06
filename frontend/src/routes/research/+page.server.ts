import { redirect } from '@sveltejs/kit';

// The workspace owns `/`; do not keep a second research landing page.
export function load() {
	throw redirect(307, '/');
}
