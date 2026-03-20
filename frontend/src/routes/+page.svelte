<script lang="ts">
	import { onMount, tick } from 'svelte';
	import type { ChatSource, Message } from '$lib/types';
	import PipelinePanel from '$lib/components/PipelinePanel.svelte';
	import ConfidenceBadge from '$lib/components/ConfidenceBadge.svelte';
	import SourceQualityIndicator from '$lib/components/SourceQualityIndicator.svelte';
	import MarkdownRenderer from '$lib/components/MarkdownRenderer.svelte';
	import { calculateConfidence } from '$lib/confidenceCalculator';
	import { getSafeExternalUrl } from '$lib/utils/url';
	import '../lib/styles/markdown.css';

	const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

	let messages: Message[] = $state([]);
	let input = $state('');
	let loading = $state(false);
	let error = $state('');
	let showPipeline = $state(true);
	let includePipelineForSession = $state(false);
	let messagesContainer: HTMLDivElement | undefined = $state();
	let copiedIndex: number | null = $state(null);

	type RenderableSource = {
		label: string;
		source: string;
		url: string | null;
		page?: number;
		classifier: string;
		key: string;
	};

	async function loadHistory() {
		try {
			const res = await fetch(`${API_URL}/history`, {
				credentials: 'include'
			});
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

		let assistantMessage: Message = {
			role: 'assistant',
			content: '',
			timestamp: Date.now()
		};
		messages = [...messages, assistantMessage];

		try {
			const url = new URL(`${API_URL}/chat`);
			if (includePipelineForSession) {
				url.searchParams.append('include_pipeline', 'true');
			}

			const res = await fetch(url.toString(), {
				method: 'POST',
				credentials: 'include',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					message: userMessage
				})
			});

			if (!res.ok) {
				throw new Error('Failed to get response');
			}

			const reader = res.body?.getReader();
			if (!reader) {
				throw new Error('No response body');
			}

			const decoder = new TextDecoder();
			let buffer = '';

			while (true) {
				const { done, value } = await reader.read();
				if (done) break;

				buffer += decoder.decode(value, { stream: true });
				const lines = buffer.split('\n');
				buffer = lines.pop() || '';

				for (const line of lines) {
					if (!line.startsWith('data: ')) continue;
					const dataStr = line.slice(6);
					try {
						const data = JSON.parse(dataStr);
						if (data.content) {
							assistantMessage.content += data.content;
							messages = [...messages.slice(0, -1), { ...assistantMessage }];
							await tick();
							scrollToBottom();
						}
						if (data.done) {
							if (data.sources) {
								assistantMessage.sources = data.sources;
							}
							if (data.pipeline) {
								assistantMessage.pipeline = data.pipeline;
								showPipeline = true;
							}
							if (data.error) {
								error = data.error;
							}
							messages = [...messages.slice(0, -1), { ...assistantMessage }];
						}
					} catch (e) {
						console.error('Failed to parse SSE data:', e);
					}
				}
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
		loading = false;
		showPipeline = false;
		fetch(`${API_URL}/history`, { method: 'DELETE', credentials: 'include' });
	}

	async function copyMessage(content: string, index: number) {
		await navigator.clipboard.writeText(content);
		copiedIndex = index;
		setTimeout(() => { copiedIndex = null; }, 2000);
	}

	function formatTime(timestamp: number): string {
		return new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
	}

	onMount(() => {
		loadHistory();
	});

	function hasPipeline(message: Message): boolean {
		return message.role === 'assistant' && message.pipeline !== undefined;
	}

	function normalizeSource(source: ChatSource | string): RenderableSource {
		if (typeof source === 'string') {
			const safeUrl = getSafeExternalUrl(source);
			return {
				label: source,
				source,
				url: safeUrl,
				classifier: safeUrl ?? source,
				key: safeUrl ?? source
			};
		}

		const safeUrl = getSafeExternalUrl(source.url);
		const label = source.label || source.source || 'Unknown source';
		const canonicalSource = source.source || source.url || label;
		return {
			label,
			source: canonicalSource,
			url: safeUrl,
			page: source.page,
			classifier: safeUrl ?? canonicalSource,
			key: safeUrl ?? canonicalSource ?? label
		};
	}

	function getRenderableSources(message: Message): RenderableSource[] {
		if (!message.sources?.length) return [];

		const deduped = new Map<string, RenderableSource>();
		for (const source of message.sources) {
			const normalized = normalizeSource(source);
			if (!deduped.has(normalized.key)) {
				deduped.set(normalized.key, normalized);
			}
		}

		return Array.from(deduped.values());
	}
</script>

<div class="chat-container">
	<nav class="nav-bar">
		<a href="/" class="nav-link active">Chat</a>
		<a href="/eval" class="nav-link">Pipeline Eval</a>
		<a href="/docs/pipeline" class="nav-link">Pipeline Docs</a>
		<a href="https://github.com/anomalyco/qna_medical_referenced" target="_blank" rel="noopener noreferrer" class="nav-github-link" aria-label="View on GitHub">
			<svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
				<path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0 0 24 12c0-6.63-5.37-12-12-12z"/>
			</svg>
		</a>
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
			{@const renderableSources = getRenderableSources(msg)}
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
				<div class="content">
					{#if msg.role === 'assistant'}
						<MarkdownRenderer content={msg.content} />
					{:else}
						{msg.content}
					{/if}
				</div>
				{#if renderableSources.length > 0}
					<div class="sources">
						<strong>Sources:</strong>
						<ol class="sources-list">
							{#each renderableSources as source, sourceIndex}
								<li class="source-item">
									<span class="source-index">{sourceIndex + 1}.</span>
									<SourceQualityIndicator source={source.classifier} />
									{#if source.url}
										<a href={source.url} target="_blank" rel="noopener noreferrer" class="source-link">
											{source.label}
										</a>
									{:else}
										<span class="source-text">{source.label}</span>
									{/if}
								</li>
							{/each}
						</ol>
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
		max-width: 1400px;
		width: 100%;
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

	.nav-github-link {
		margin-left: auto;
		display: flex;
		align-items: center;
		padding: 0.5rem;
		color: #666;
		border-radius: 4px;
	}

	.nav-github-link:hover {
		background: #f0f0f0;
		color: #333;
	}

	.nav-github-link svg {
		width: 20px;
		height: 20px;
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
		max-width: 90%;
	}

	@media (max-width: 768px) {
		.message {
			max-width: 95%;
		}
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
		display: grid;
		gap: 0.5rem;
	}

	.sources-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.45rem;
	}

	.source-item {
		display: grid;
		grid-template-columns: auto auto minmax(0, 1fr);
		align-items: start;
		gap: 0.5rem;
	}

	.source-index {
		min-width: 1.5rem;
		font-weight: 600;
		color: #6b7280;
	}

	.source-link,
	.source-text {
		font-size: 0.95rem;
		color: #4b5563;
		word-break: break-word;
	}

	.source-link {
		text-decoration: none;
	}

	.source-link:hover {
		text-decoration: underline;
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

	/* Optimal line length for wide screens */
	@media (min-width: 1400px) {
		.message.assistant .content {
			max-width: 75ch;
		}
	}
</style>
