import hljs from 'highlight.js/lib/core';
import bash from 'highlight.js/lib/languages/bash';
import javascript from 'highlight.js/lib/languages/javascript';
import json from 'highlight.js/lib/languages/json';
import plaintext from 'highlight.js/lib/languages/plaintext';
import python from 'highlight.js/lib/languages/python';
import typescript from 'highlight.js/lib/languages/typescript';
import xml from 'highlight.js/lib/languages/xml';

const LANGUAGE_LOADERS = {
	bash,
	javascript,
	json,
	plaintext,
	python,
	typescript,
	xml
} as const;

const LANGUAGE_ALIASES: Record<string, keyof typeof LANGUAGE_LOADERS> = {
	bash: 'bash',
	console: 'bash',
	html: 'xml',
	js: 'javascript',
	javascript: 'javascript',
	json: 'json',
	plaintext: 'plaintext',
	py: 'python',
	python: 'python',
	sh: 'bash',
	shell: 'bash',
	text: 'plaintext',
	ts: 'typescript',
	typescript: 'typescript',
	xml: 'xml'
};

let registered = false;

function ensureLanguagesRegistered() {
	if (registered) return;

	for (const [language, loader] of Object.entries(LANGUAGE_LOADERS)) {
		hljs.registerLanguage(language, loader);
	}

	registered = true;
}

export function normalizeLanguage(language: string | undefined): keyof typeof LANGUAGE_LOADERS | null {
	if (!language) return null;

	const normalized = language.trim().toLowerCase().split(/\s+/, 1)[0];
	return LANGUAGE_ALIASES[normalized] ?? null;
}

export function highlightCode(code: string, language: string | undefined) {
	ensureLanguagesRegistered();

	const normalizedLanguage = normalizeLanguage(language);
	if (!normalizedLanguage) {
		return {
			language: null,
			html: hljs.highlight(code, { language: 'plaintext', ignoreIllegals: true }).value
		};
	}

	return {
		language: normalizedLanguage,
		html: hljs.highlight(code, { language: normalizedLanguage, ignoreIllegals: true }).value
	};
}
