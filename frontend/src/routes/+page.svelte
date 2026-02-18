<script lang="ts">
	import { onMount } from 'svelte';
	import type { Message } from '$lib/types';
	import PipelinePanel from '$lib/components/PipelinePanel.svelte';

	let messages: Message[] = $state([]);
	let input = $state('');
	let loading = $state(false);
	let sessionId = $state('');
	let error = $state('');
	let showPipeline = $state(false);
	let includePipelineForSession = $state(false);

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
			// Build URL with pipeline parameter if enabled
			const url = new URL(`${API_URL}/chat`);
			if (includePipelineForSession) {
				url.searchParams.append('include_pipeline', 'true');
			}

			const res = await fetch(url.toString(), {
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
				sources: data.sources,
				pipeline: data.pipeline
			}];

			// Auto-open pipeline panel if data is available
			if (data.pipeline && includePipelineForSession) {
				showPipeline = true;
			}
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
		showPipeline = false;
		fetch(`${API_URL}/history/${sessionId}`, { method: 'DELETE' });
	}

	onMount(() => {
		sessionId = generateSessionId();
		loadHistory();
	});

	function hasPipeline(message: Message): boolean {
		return message.role === 'assistant' && message.pipeline !== undefined;
	}
</script>

<div class="chat-container">
	<header>
		<div class="header-left">
			<h1>Health Screening Q&A</h1>
			<label class="pipeline-toggle">
				<input type="checkbox" bind:checked={includePipelineForSession} />
				<span>Show pipeline details</span>
			</label>
		</div>
		<button onclick={clearChat}>New Chat</button>
	</header>

	<div class="messages">
		{#if messages.length === 0}
			<div class="welcome">
				<p>Ask me anything about your health screening results.</p>
			</div>
		{/if}

		{#each messages as msg, index}
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
				{#if hasPipeline(msg)}
					<button
						class="pipeline-btn"
						onclick={() => (showPipeline = !showPipeline)}
						class:active={showPipeline}
					>
						{showPipeline ? 'Hide' : 'Show'} Pipeline Details
					</button>
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

	{#if showPipeline && messages.length > 0}
		{@const lastAssistantMsg = [...messages].reverse().find((m) => m.role === 'assistant' && m.pipeline)}
		{#if lastAssistantMsg?.pipeline}
			<PipelinePanel pipeline={lastAssistantMsg.pipeline} isOpen={showPipeline} />
		{/if}
	{/if}
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
		flex-wrap: wrap;
		gap: 1rem;
	}

	.header-left {
		display: flex;
		flex-direction: column;
		gap: 0.5rem;
	}

	header h1 {
		font-size: 1.5rem;
		margin: 0;
	}

	.pipeline-toggle {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		font-size: 0.9rem;
		cursor: pointer;
		user-select: none;
	}

	.pipeline-toggle input[type='checkbox'] {
		cursor: pointer;
		width: 16px;
		height: 16px;
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

	.pipeline-btn {
		margin-top: 0.75rem;
		padding: 0.5rem 1rem;
		background: #e3f2fd;
		color: #1976d2;
		border: 1px solid #2196f3;
		border-radius: 4px;
		cursor: pointer;
		font-size: 0.85rem;
		font-weight: 500;
		transition: all 0.2s ease;
	}

	.pipeline-btn:hover {
		background: #bbdefb;
		border-color: #1976d2;
	}

	.pipeline-btn.active {
		background: #1976d2;
		color: white;
		border-color: #1565c0;
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
