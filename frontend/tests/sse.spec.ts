import { test, expect } from '@playwright/test';
import { SseDecoder, classifyStreamOutcome } from '../src/lib/utils/sse';
import { normalizeApiBase, resolveApiUrl } from '../src/lib/utils/api';

const encoder = new TextEncoder();

test.describe('SSE decoder', () => {
	test('handles UTF-8 and frame boundaries split across chunks', () => {
		const bytes = encoder.encode('data: {"content":"héllo","done":false}\n\n');
		const splitAt = bytes.indexOf(0xc3) + 1; // inside the two-byte é
		const decoder = new SseDecoder();
		const first = decoder.push(bytes.slice(0, splitAt));
		const second = decoder.push(bytes.slice(splitAt));
		const frames = [...first, ...second];

		expect(frames).toHaveLength(1);
		expect(JSON.parse(frames[0])).toEqual({ content: 'héllo', done: false });
	});

	test('handles CRLF boundaries and multiple frames', () => {
		const decoder = new SseDecoder();
		const frames = decoder.push(
			encoder.encode('data: {"a":1}\r\n\r\ndata: {"b":2}\r\n\r\n')
		);
		expect(frames.map((frame) => JSON.parse(frame))).toEqual([{ a: 1 }, { b: 2 }]);
	});

	test('joins multi-line data and ignores comments/other fields', () => {
		const decoder = new SseDecoder();
		const frames = decoder.push(
			encoder.encode(': keepalive\nevent: message\ndata: {"a":\ndata: 1}\n\n')
		);
		expect(frames).toEqual(['{"a":\n1}']);
	});

	test('finish flushes a trailing frame but EOF is still incomplete', () => {
		const decoder = new SseDecoder();
		const frames = decoder.push(encoder.encode('data: {"content":"partial","done":false}'));
		expect(frames).toEqual([]);
		const flushed = decoder.finish();
		expect(flushed).toHaveLength(1);
		expect(classifyStreamOutcome(flushed)).toBe('incomplete');
	});
});

test.describe('stream outcome', () => {
	test('requires an explicit terminal event', () => {
		expect(classifyStreamOutcome(['{"content":"a","done":false}'])).toBe('incomplete');
		expect(classifyStreamOutcome(['{"content":"a","done":false}', '{"done":true}'])).toBe(
			'complete'
		);
		expect(
			classifyStreamOutcome([
				'{"content":"a","done":false}',
				'{"done":true,"error":"failed","error_code":"chat_failed"}'
			])
		).toBe('error');
	});

	test('malformed frames cannot establish success', () => {
		expect(classifyStreamOutcome(['not-json', '{"content":"a"}'])).toBe('incomplete');
	});
});

test.describe('API URL resolution', () => {
	const origin = 'https://lab.example.com';

	test('absolute, root-relative and empty bases resolve without throwing', () => {
		expect(resolveApiUrl('https://api.example.com/', '/chat', origin)).toBe(
			'https://api.example.com/chat'
		);
		expect(resolveApiUrl('/private/api', '/chat', origin)).toBe(
			'https://lab.example.com/private/api/chat'
		);
		expect(resolveApiUrl('', '/chat', origin)).toBe('https://lab.example.com/chat');
	});

	test('normalizes trailing separators and rejects unsupported schemes', () => {
		expect(normalizeApiBase(' https://api.example.com/// ')).toBe('https://api.example.com');
		expect(normalizeApiBase('/private/api/')).toBe('/private/api');
		expect(normalizeApiBase('ftp://api.example.com')).toBe('');
		expect(normalizeApiBase('api.example.com')).toBe('');
	});
});
