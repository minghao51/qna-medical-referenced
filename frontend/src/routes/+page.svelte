<script lang="ts">
	import { onMount, tick } from 'svelte';
	import type { ChatSource, Message, SourceDomainType } from '$lib/types';
	import AppShell from '$lib/components/AppShell.svelte';
	import PipelinePanel from '$lib/components/PipelinePanel.svelte';
	import ConfidenceBadge from '$lib/components/ConfidenceBadge.svelte';
	import SourceQualityIndicator from '$lib/components/SourceQualityIndicator.svelte';
	import SourceDistributionChart from '$lib/components/SourceDistributionChart.svelte';
	import MarkdownRenderer from '$lib/components/MarkdownRenderer.svelte';
	import { calculateConfidence, getDomainType } from '$lib/confidenceCalculator';
	import { getSafeExternalUrl } from '$lib/utils/url';
	import '../lib/styles/markdown.css';

	const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

	let messages: Message[] = $state([]);
	let input = $state('');
	let loading = $state(false);
	let error = $state('');
	let showPipeline = $state(true);
	let includePipelineForSession = $state(true);
	let messagesContainer: HTMLDivElement | undefined = $state();
	let copiedIndex: number | null = $state(null);
	let sourcePanelTabs: Record<number, 'citations' | 'distribution'> = $state({});

	type RenderableSource = {
		canonicalLabel: string;
		displayLabel: string;
		source: string;
		url: string | null;
		page?: number;
		sourceType: string;
		sourceClass: string;
		domain: string | null;
		domainType: SourceDomainType;
		contentType?: string;
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
				headers: {
					'Content-Type': 'application/json',
					Accept: 'text/event-stream'
				},
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
						// Always update content, even if empty (for final event)
						if (data.content !== undefined) {
							assistantMessage.content += data.content;
						}
						// Check if stream is done
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
						}
						// Update messages after processing each event
						messages = [...messages.slice(0, -1), { ...assistantMessage }];
						await tick();
						scrollToBottom();
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

	function formatTitleCase(value: string): string {
		return value
			.split(/[_\s-]+/)
			.filter(Boolean)
			.map((part) => part.charAt(0).toUpperCase() + part.slice(1))
			.join(' ');
	}

	function inferSourceType(source: string): string {
		const lowered = source.toLowerCase();
		if (lowered.endsWith('.pdf')) return 'pdf';
		if (lowered.endsWith('.csv')) return 'reference_csv';
		if (lowered.endsWith('.md') || lowered.endsWith('.html')) return 'html';
		return 'other';
	}

	function sourceTypeLabel(sourceType: string): string {
		const labels: Record<string, string> = {
			pdf: 'PDF',
			html: 'HTML',
			reference_csv: 'Reference CSV',
			other: 'Other'
		};
		return labels[sourceType] ?? formatTitleCase(sourceType);
	}

	function sourceClassLabel(sourceClass: string): string {
		const labels: Record<string, string> = {
			guideline_pdf: 'Guideline PDF',
			guideline_html: 'Guideline HTML',
			reference_csv: 'Reference CSV',
			index_page: 'Index Page',
			unknown: 'Unknown'
		};
		return labels[sourceClass] ?? formatTitleCase(sourceClass);
	}

	function getSourceTab(index: number): 'citations' | 'distribution' {
		return sourcePanelTabs[index] ?? 'citations';
	}

	function setSourceTab(index: number, tab: 'citations' | 'distribution') {
		sourcePanelTabs = { ...sourcePanelTabs, [index]: tab };
	}

	function normalizeSource(source: ChatSource | string): RenderableSource {
		if (typeof source === 'string') {
			const safeUrl = getSafeExternalUrl(source);
			const domain = safeUrl ? new URL(safeUrl).hostname.toLowerCase() : null;
			const sourceType = inferSourceType(source);
			return {
				canonicalLabel: source,
				displayLabel: source,
				source,
				url: safeUrl,
				sourceType,
				sourceClass: sourceType === 'reference_csv' ? 'reference_csv' : 'unknown',
				domain,
				domainType: domain ? getDomainType(domain) : 'unknown',
				key: `${safeUrl ?? source}::`
			};
		}

		const safeUrl = getSafeExternalUrl(source.source_url || source.url);
		const canonicalLabel =
			source.canonical_label || source.display_label || source.label || source.source || 'Unknown source';
		const displayLabel = source.display_label || source.label || canonicalLabel;
		const canonicalSource = source.source || source.source_url || source.url || canonicalLabel;
		const domain = source.domain || (safeUrl ? new URL(safeUrl).hostname.toLowerCase() : null);
		const sourceType = source.source_type || inferSourceType(canonicalSource);
		const sourceClass =
			source.source_class || (sourceType === 'reference_csv' ? 'reference_csv' : 'unknown');
		return {
			canonicalLabel,
			displayLabel,
			source: canonicalSource,
			url: safeUrl,
			page: source.page,
			sourceType,
			sourceClass,
			domain,
			domainType: source.domain_type || (domain ? getDomainType(domain) : 'unknown'),
			contentType: source.content_type,
			key: `${canonicalSource}::${source.page ?? ''}`
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

	function buildDistribution(
		sources: RenderableSource[],
		field: 'sourceType' | 'sourceClass'
	): Record<string, number> {
		return sources.reduce<Record<string, number>>((acc, source) => {
			const value = source[field];
			if (!value || value === 'unknown') return acc;
			const label = field === 'sourceType' ? sourceTypeLabel(value) : sourceClassLabel(value);
			acc[label] = (acc[label] ?? 0) + 1;
			return acc;
		}, {});
	}
</script>

<AppShell current="/" wide={true}>
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

	<div class="messages" bind:this={messagesContainer}>
		{#if messages.length === 0}
			<div class="welcome">
				<p>Ask me anything about your health screening results.</p>
			</div>
		{/if}

		{#each messages as msg, index}
			{@const renderableSources = getRenderableSources(msg)}
			{@const typeDistribution = buildDistribution(renderableSources, 'sourceType')}
			{@const classDistribution = buildDistribution(renderableSources, 'sourceClass')}
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
					<div class="sources-panel">
						<div class="sources-panel-header">
							<strong>Sources</strong>
							<div class="source-tabs">
								<button
									type="button"
									class:active={getSourceTab(index) === 'citations'}
									onclick={() => setSourceTab(index, 'citations')}
								>
									Citations
								</button>
								<button
									type="button"
									class:active={getSourceTab(index) === 'distribution'}
									onclick={() => setSourceTab(index, 'distribution')}
								>
									Distribution
								</button>
							</div>
						</div>
						{#if getSourceTab(index) === 'citations'}
							<ol class="sources-list">
								{#each renderableSources as source, sourceIndex}
									<li class="source-card">
										<div class="source-card-top">
											<span class="source-index">{sourceIndex + 1}.</span>
											<div class="source-title-wrap">
												{#if source.url}
													<a href={source.url} target="_blank" rel="noopener noreferrer" class="source-link">
														{source.displayLabel}
													</a>
												{:else}
													<span class="source-text">{source.displayLabel}</span>
												{/if}
												{#if source.domain}
													<span class="source-domain">{source.domain}</span>
												{/if}
											</div>
										</div>
										<div class="source-badges">
											<span class="source-type-pill">{sourceTypeLabel(source.sourceType)}</span>
											{#if source.sourceClass !== 'unknown'}
												<span class="source-class-pill">{sourceClassLabel(source.sourceClass)}</span>
											{/if}
											<SourceQualityIndicator
												source={source.domain ?? source.url ?? source.source}
												sourceType={source.sourceType}
												domainType={source.domainType}
											/>
											{#if source.contentType}
												<span class="source-meta-pill">{formatTitleCase(source.contentType)}</span>
											{/if}
										</div>
									</li>
								{/each}
							</ol>
						{:else}
							<div class="distribution-grid">
								{#if Object.keys(typeDistribution).length > 0}
									<div class="distribution-card">
										<SourceDistributionChart distribution={typeDistribution} title="Source Types" height={180} />
									</div>
								{/if}
								{#if Object.keys(classDistribution).length > 0}
									<div class="distribution-card">
										<SourceDistributionChart distribution={classDistribution} title="Source Classes" height={180} />
									</div>
								{/if}
								{#if Object.keys(typeDistribution).length === 0 && Object.keys(classDistribution).length === 0}
									<p class="distribution-empty">No structured source distribution available yet.</p>
								{/if}
							</div>
						{/if}
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
</AppShell>

<style>
	.chat-container {
		width: 100%;
		min-height: calc(100vh - 8rem);
		display: flex;
		flex-direction: column;
		gap: 1rem;
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
		font-size: 1.85rem;
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
		padding: 0.65rem 0.95rem;
		background: white;
		border: 1px solid var(--border-color);
		border-radius: 999px;
		cursor: pointer;
	}

	header button:hover {
		background: var(--surface-subtle);
	}

	.messages {
		flex: 1;
		overflow-y: auto;
		padding: 1rem;
		border: 1px solid var(--border-color);
		border-radius: 18px;
		background: white;
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

	.sources-panel {
		margin-top: 0.5rem;
		font-size: 0.85rem;
		color: #666;
		display: grid;
		gap: 0.5rem;
		padding: 0.75rem;
		border: 1px solid #dbe3ec;
		border-radius: 0.85rem;
		background: #f8fbfd;
	}

	.sources-panel-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
	}

	.source-tabs {
		display: flex;
		gap: 0.4rem;
		flex-wrap: wrap;
	}

	.source-tabs button {
		border: 1px solid #c8d6e5;
		background: white;
		color: #456;
		padding: 0.35rem 0.7rem;
		border-radius: 999px;
		font-size: 0.78rem;
		cursor: pointer;
	}

	.source-tabs button.active {
		background: #0f766e;
		border-color: #0f766e;
		color: white;
	}

	.sources-list {
		list-style: none;
		margin: 0;
		padding: 0;
		display: grid;
		gap: 0.45rem;
	}

	.source-card {
		display: grid;
		gap: 0.55rem;
		padding: 0.75rem;
		border-radius: 0.8rem;
		background: white;
		border: 1px solid #e2e8f0;
	}

	.source-card-top {
		display: grid;
		grid-template-columns: auto minmax(0, 1fr);
		align-items: start;
		gap: 0.65rem;
	}

	.source-title-wrap {
		display: grid;
		gap: 0.25rem;
	}

	.source-index {
		min-width: 1.5rem;
		font-weight: 600;
		color: #6b7280;
	}

	.source-badges {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}

	.source-type-pill,
	.source-class-pill,
	.source-meta-pill {
		display: inline-flex;
		align-items: center;
		padding: 0.2rem 0.5rem;
		border-radius: 999px;
		font-size: 0.72rem;
		font-weight: 600;
	}

	.source-type-pill {
		background: #dbeafe;
		color: #1d4ed8;
	}

	.source-class-pill {
		background: #dcfce7;
		color: #15803d;
	}

	.source-meta-pill {
		background: #fef3c7;
		color: #b45309;
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

	.source-domain {
		font-size: 0.8rem;
		color: #64748b;
	}

	.distribution-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: 0.75rem;
	}

	.distribution-card {
		padding: 0.5rem;
		background: white;
		border: 1px solid #e2e8f0;
		border-radius: 0.8rem;
	}

	.distribution-empty {
		margin: 0;
		color: #64748b;
		font-size: 0.9rem;
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
		padding: 1rem;
		border: 1px solid var(--border-color);
		border-radius: 18px;
		background: white;
	}

	.input-area textarea {
		flex: 1;
		padding: 0.75rem;
		border: 1px solid var(--border-color);
		border-radius: 14px;
		resize: none;
		font-family: inherit;
		font-size: 1rem;
		background: var(--surface-subtle);
	}

	.input-area textarea:focus {
		outline: none;
		border-color: #2196f3;
	}

	.input-area button {
		padding: 0.75rem 1.5rem;
		background: #1f4f82;
		color: white;
		border: none;
		border-radius: 999px;
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
