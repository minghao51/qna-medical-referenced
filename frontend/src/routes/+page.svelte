<script lang="ts">
	import { onMount, tick } from 'svelte';
	import type { Message } from '$lib/types';
	import PipelinePanel from '$lib/components/PipelinePanel.svelte';
	import ConfidenceBadge from '$lib/components/ConfidenceBadge.svelte';
	import SourceQualityIndicator from '$lib/components/SourceQualityIndicator.svelte';
	import { calculateConfidence } from '$lib/confidenceCalculator';

	const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

	let messages: Message[] = $state([]);
	let input = $state('');
	let loading = $state(false);
	let sessionId = $state('');
	let error = $state('');
	let showPipeline = $state(false);
	let includePipelineForSession = $state(false);
	let messagesContainer: HTMLDivElement | undefined = $state();
	let copiedIndex: number | null = $state(null);

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
				await tick();
				scrollToBottom();
			}
		} catch (e) {
			console.error('Failed to load history:', e);
		}
	}

	async function scrollToBottom() {
		if (messagesContainer) {
			messagesContainer.scrollTop = messagesContainer.scrollHeight;
		}
	}

	async function sendMessage() {
		if (!input.trim() || loading) return;

		const userMessage = input.trim();
		input = '';
		loading = true;
		error = '';

		messages = [...messages, { role: 'user', content: userMessage, timestamp: Date.now() }];
		await tick();
		scrollToBottom();

		try {
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
				pipeline: data.pipeline,
				timestamp: Date.now()
			}];

			if (data.pipeline && includePipelineForSession) {
				showPipeline = true;
			}
			await tick();
			scrollToBottom();
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
		loading = false;
		showPipeline = false;
		fetch(`${API_URL}/history/${sessionId}`, { method: 'DELETE' });
	}

	async function copyMessage(content: string, index: number) {
		await navigator.clipboard.writeText(content);
		copiedIndex = index;
		setTimeout(() => { copiedIndex = null; }, 2000);
	}

	function formatTime(timestamp: number): string {
		return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
	}

	function escapeHtml(text: string): string {
		return text
			.replaceAll('&', '&amp;')
			.replaceAll('<', '&lt;')
			.replaceAll('>', '&gt;')
			.replaceAll('"', '&quot;')
			.replaceAll("'", '&#39;');
	}

	function renderMarkdown(text: string): string {
		const escaped = escapeHtml(text);
		return escaped
			.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
			.replace(/\*(.*?)\*/g, '<em>$1</em>')
			.replace(/`(.*?)`/g, '<code>$1</code>')
			.replace(/\n/g, '<br>');
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
	<nav class="nav-bar">
		<a href="/" class="nav-link active">Chat</a>
		<a href="/eval" class="nav-link">Pipeline Eval</a>
	</nav>
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

	<div class="messages" bind:this={messagesContainer}>
		{#if messages.length === 0}
			<div class="welcome">
				<p>Ask me anything about your health screening results.</p>
			</div>
		{/if}

		{#each messages as msg, index}
			<div class="message {msg.role}">
				<div class="message-header">
					<span class="role-label">{msg.role === 'user' ? 'You' : 'Assistant'}</span>
					{#if msg.timestamp}
						<span class="timestamp">{formatTime(msg.timestamp)}</span>
					{/if}
					{#if msg.role === 'assistant' && msg.pipeline}
						{@const conf = calculateConfidence(msg.pipeline)}
						<ConfidenceBadge level={conf.level} score={conf.overall} showScore={false} />
					{/if}
					{#if msg.role === 'assistant'}
						<button
							class="copy-btn"
							onclick={() => copyMessage(msg.content, index)}
							title="Copy message"
						>
							{copiedIndex === index ? '✓ Copied' : 'Copy'}
						</button>
					{/if}
				</div>
				<div class="content">{@html msg.role === 'assistant' ? renderMarkdown(msg.content) : msg.content}</div>
				{#if msg.sources && msg.sources.length > 0}
					<div class="sources">
						<strong>Sources:</strong>
						{#each msg.sources as source}
							<span class="source">
								<SourceQualityIndicator {source} />
								<span class="source-text">{source}</span>
							</span>
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
				<div class="typing-indicator">
					<span></span>
					<span></span>
					<span></span>
				</div>
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

	.nav-bar {
		display: flex;
		gap: 1rem;
		margin-bottom: 1rem;
		padding-bottom: 0.5rem;
		border-bottom: 1px solid #eee;
	}

	.nav-link {
		padding: 0.5rem 1rem;
		text-decoration: none;
		color: #666;
		border-radius: 4px;
		font-weight: 500;
	}

	.nav-link:hover {
		background: #f0f0f0;
	}

	.nav-link.active {
		background: #e3f2fd;
		color: #1976d2;
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

	.message-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.5rem;
		font-size: 0.8rem;
	}

	.role-label {
		font-weight: 600;
		color: #666;
	}

	.timestamp {
		color: #999;
	}

	.copy-btn {
		margin-left: auto;
		padding: 0.2rem 0.5rem;
		background: transparent;
		border: 1px solid #ddd;
		border-radius: 3px;
		cursor: pointer;
		font-size: 0.75rem;
		color: #666;
		transition: all 0.2s;
	}

	.copy-btn:hover {
		background: #e0e0e0;
	}

	.typing-indicator {
		display: flex;
		gap: 4px;
		padding: 0.5rem;
	}

	.typing-indicator span {
		width: 8px;
		height: 8px;
		background: #666;
		border-radius: 50%;
		animation: typing 1.4s infinite ease-in-out;
	}

	.typing-indicator span:nth-child(1) {
		animation-delay: 0s;
	}

	.typing-indicator span:nth-child(2) {
		animation-delay: 0.2s;
	}

	.typing-indicator span:nth-child(3) {
		animation-delay: 0.4s;
	}

	@keyframes typing {
		0%, 60%, 100% {
			transform: translateY(0);
			opacity: 0.4;
		}
		30% {
			transform: translateY(-6px);
			opacity: 1;
		}
	}

	.content {
		white-space: pre-wrap;
		line-height: 1.5;
	}

	.content :global(code) {
		background: #e0e0e0;
		padding: 0.1rem 0.3rem;
		border-radius: 3px;
		font-family: monospace;
		font-size: 0.9em;
	}

	.content :global(strong) {
		font-weight: 600;
	}

	.sources {
		margin-top: 0.5rem;
		font-size: 0.85rem;
		color: #666;
	}

	.source {
		display: inline-flex;
		align-items: center;
		gap: 0.35rem;
		background: #e0e0e0;
		padding: 0.2rem 0.5rem;
		border-radius: 3px;
		margin: 0.2rem 0.2rem 0 0;
		font-size: 0.75rem;
	}

	.source-text {
		max-width: 200px;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
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
