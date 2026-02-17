<script lang="ts">
	import { onMount } from 'svelte';

	interface Message {
		role: 'user' | 'assistant';
		content: string;
		sources?: string[];
	}

	let messages: Message[] = $state([]);
	let input = $state('');
	let loading = $state(false);
	let sessionId = $state('');
	let error = $state('');

	const API_URL = 'http://localhost:8000';

	function generateSessionId() {
		let id = localStorage.getItem('chat_session_id');
		if (!id) {
			id = 'session_' + Date.now() + '_' + Math.random().toString(36).substring(2, 9);
			localStorage.setItem('chat_session_id', id);
		}
		return id;
	}

	async function loadHistory() {
		try {
			const res = await fetch(`${API_URL}/history/${sessionId}`);
			if (res.ok) {
				const data = await res.json();
				messages = data.history;
			}
		} catch (e) {
			console.error('Failed to load history:', e);
		}
	}

	async function sendMessage() {
		if (!input.trim() || loading) return;
		
		const userMessage = input.trim();
		input = '';
		loading = true;
		error = '';

		messages = [...messages, { role: 'user', content: userMessage }];

		try {
			const res = await fetch(`${API_URL}/chat`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					message: userMessage,
					session_id: sessionId
				})
			});

			if (!res.ok) {
				throw new Error('Failed to get response');
			}

			const data = await res.json();
			messages = [...messages, {
				role: 'assistant',
				content: data.response,
				sources: data.sources
			}];
		} catch (e) {
			error = 'Failed to send message. Make sure the API is running.';
			console.error(e);
		} finally {
			loading = false;
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			sendMessage();
		}
	}

	function clearChat() {
		messages = [];
		fetch(`${API_URL}/history/${sessionId}`, { method: 'DELETE' });
	}

	onMount(() => {
		sessionId = generateSessionId();
		loadHistory();
	});
</script>

<div class="chat-container">
	<header>
		<h1>Health Screening Q&A</h1>
		<button onclick={clearChat}>New Chat</button>
	</header>

	<div class="messages">
		{#if messages.length === 0}
			<div class="welcome">
				<p>Ask me anything about your health screening results.</p>
			</div>
		{/if}
		
		{#each messages as msg}
			<div class="message {msg.role}">
				<div class="content">{msg.content}</div>
				{#if msg.sources && msg.sources.length > 0}
					<div class="sources">
						<strong>Sources:</strong>
						{#each msg.sources as source}
							<span class="source">{source}</span>
						{/each}
					</div>
				{/if}
			</div>
		{/each}
		
		{#if loading}
			<div class="message assistant loading">
				<div class="content">Thinking...</div>
			</div>
		{/if}
		
		{#if error}
			<div class="error">{error}</div>
		{/if}
	</div>

	<div class="input-area">
		<textarea
			bind:value={input}
			onkeydown={handleKeydown}
			placeholder="Ask a question..."
			rows="2"
			disabled={loading}
		></textarea>
		<button onclick={sendMessage} disabled={loading || !input.trim()}>
			Send
		</button>
	</div>
</div>

<style>
	.chat-container {
		max-width: 800px;
		margin: 0 auto;
		height: 100vh;
		display: flex;
		flex-direction: column;
		padding: 1rem;
		box-sizing: border-box;
	}

	header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		margin-bottom: 1rem;
	}

	header h1 {
		font-size: 1.5rem;
		margin: 0;
	}

	header button {
		padding: 0.5rem 1rem;
		background: #f0f0f0;
		border: none;
		border-radius: 4px;
		cursor: pointer;
	}

	header button:hover {
		background: #e0e0e0;
	}

	.messages {
		flex: 1;
		overflow-y: auto;
		padding: 1rem 0;
	}

	.welcome {
		text-align: center;
		color: #666;
		margin-top: 2rem;
	}

	.message {
		margin-bottom: 1rem;
		padding: 1rem;
		border-radius: 8px;
		max-width: 85%;
	}

	.message.user {
		background: #e3f2fd;
		margin-left: auto;
	}

	.message.assistant {
		background: #f5f5f5;
		margin-right: auto;
	}

	.message.loading {
		opacity: 0.6;
	}

	.content {
		white-space: pre-wrap;
		line-height: 1.5;
	}

	.sources {
		margin-top: 0.5rem;
		font-size: 0.85rem;
		color: #666;
	}

	.source {
		display: inline-block;
		background: #e0e0e0;
		padding: 0.2rem 0.5rem;
		border-radius: 3px;
		margin: 0.2rem 0.2rem 0 0;
		font-size: 0.75rem;
	}

	.error {
		color: #d32f2f;
		padding: 0.5rem;
		background: #ffebee;
		border-radius: 4px;
	}

	.input-area {
		display: flex;
		gap: 0.5rem;
		padding-top: 1rem;
		border-top: 1px solid #eee;
	}

	.input-area textarea {
		flex: 1;
		padding: 0.75rem;
		border: 1px solid #ddd;
		border-radius: 8px;
		resize: none;
		font-family: inherit;
		font-size: 1rem;
	}

	.input-area textarea:focus {
		outline: none;
		border-color: #2196f3;
	}

	.input-area button {
		padding: 0.75rem 1.5rem;
		background: #2196f3;
		color: white;
		border: none;
		border-radius: 8px;
		cursor: pointer;
		font-weight: 500;
	}

	.input-area button:hover:not(:disabled) {
		background: #1976d2;
	}

	.input-area button:disabled {
		background: #ccc;
		cursor: not-allowed;
	}
</style>
