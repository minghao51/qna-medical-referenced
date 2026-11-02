import type { Message } from './types';

/**
 * Per-layout, in-memory chat state. Deliberately not a module singleton or
 * persistent store: ordinary in-app navigation keeps the conversation, while
 * a hard reload honestly loses sources/traces.
 */
export function createChatState() {
	let messages = $state<Message[]>([]);
	let draft = $state('');

	return {
		get messages() {
			return messages;
		},
		set messages(next: Message[]) {
			messages = next;
		},
		get draft() {
			return draft;
		},
		set draft(next: string) {
			draft = next;
		}
	};
}

export type ChatState = ReturnType<typeof createChatState>;
