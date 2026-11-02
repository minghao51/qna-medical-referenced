<script lang="ts">
	import { getContext, onMount, tick } from 'svelte';
	import type { ChatSource, Message, MessageStatus, SourceDomainType, PipelineTrace as PipelineTraceType } from '$lib/types';
	import AppShell from '$lib/components/AppShell.svelte';
	import SourceQualityIndicator from '$lib/components/SourceQualityIndicator.svelte';
	import { getDomainType } from '$lib/confidenceCalculator';
	import { SseDecoder } from '$lib/utils/sse';
	import type { ChatState } from '$lib/conversation-state.svelte';
	import {
		fetchHealthStatus,
		getHistory,
		clearHistory,
		chatStreamUrl,
		chatFetchRequest,
		parseApiError
	} from '$lib/utils/api';
	import { getSafeExternalUrl } from '$lib/utils/url';
	import type { HealthResponse } from '$lib/types';
	import '../../lib/styles/markdown.css';

	const MAX_MESSAGE_LENGTH = 2000;
	const chat = getContext<ChatState>('fieldnote-chat');

	let messages: Message[] = $state(chat.messages);
	let input = $state(chat.draft);
	let announcement = $state('');
	let inspectedIndex = $state<number | null>(null);
	let autoFollow = $state(true);
	let hydrated = $state(false);
	let loading = $state(false);
	let error = $state('');
	let showPipeline = $state(false);
	let includePipelineForSession = $state(true);
	let messagesContainer: HTMLDivElement | undefined = $state();
	let copiedIndex: number | null = $state(null);
	let sourcePanelTabs: Record<number, 'citations' | 'distribution'> = $state({});
	let healthStatus: HealthResponse | null = $state(null);
	let operationalNotice = $state('');
	let PipelinePanelComponent = $state<typeof import('$lib/components/PipelinePanel.svelte').default | null>(null);
	let SourceDistributionChartComponent = $state<typeof import('$lib/components/SourceDistributionChart.svelte').default | null>(null);
	let MarkdownRendererComponent = $state<typeof import('$lib/components/MarkdownRenderer.svelte').default | null>(null);
	let activeStreamController: AbortController | null = null;
	let requestGeneration = 0;

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
		if (chat.messages.length > 0) {
			messages = chat.messages;
			await tick();
			scrollToBottom();
			return;
		}
		try {
			const data = await getHistory();
			if ((data.history as Message[]).some((message) => message.role === 'assistant')) {
				void ensureMarkdownRenderer();
			}
			messages = data.history as Message[];
			await tick();
			scrollToBottom();
		} catch (e) {
			console.error('Failed to load history:', e);
		}
	}

	async function loadHealth() {
		try {
			healthStatus = await fetchHealthStatus();
			if (!healthStatus.ready) {
				operationalNotice = 'Backend is reachable, but the runtime index is not ready yet.';
			} else {
				operationalNotice = '';
			}
		} catch (e) {
			operationalNotice = e instanceof Error ? e.message : 'Backend status unavailable.';
		}
	}

	async function scrollToBottom() {
		if (messagesContainer) {
			messagesContainer.scrollTop = messagesContainer.scrollHeight;
			autoFollow = true;
		}
	}

	function handleMessagesScroll() {
		if (!messagesContainer) return;
		autoFollow =
			messagesContainer.scrollHeight - messagesContainer.scrollTop - messagesContainer.clientHeight < 80;
	}

	async function ensurePipelinePanel() {
		if (!PipelinePanelComponent) {
			PipelinePanelComponent = (await import('$lib/components/PipelinePanel.svelte')).default;
		}
	}

	async function ensureSourceDistributionChart() {
		if (!SourceDistributionChartComponent) {
			SourceDistributionChartComponent = (await import('$lib/components/SourceDistributionChart.svelte')).default;
		}
	}

	async function ensureMarkdownRenderer() {
		if (!MarkdownRendererComponent) {
			MarkdownRendererComponent = (await import('$lib/components/MarkdownRenderer.svelte')).default;
		}
	}

	function abortActiveStream() {
		if (activeStreamController) {
			activeStreamController.abort();
			activeStreamController = null;
		}
	}

	async function sendMessage() {
		if (!input.trim() || loading) return;

		const userMessage = input.trim();
		if (userMessage.length > MAX_MESSAGE_LENGTH) {
			error = `Message too long (${userMessage.length}/${MAX_MESSAGE_LENGTH} characters).`;
			return;
		}
		input = '';
		loading = true;
		error = '';

		const generation = ++requestGeneration;
		abortActiveStream();
		inspectedIndex = null;
		const controller = new AbortController();
		activeStreamController = controller;

		messages = [...messages, { role: 'user', content: userMessage, timestamp: Date.now() }];
		await tick();
		scrollToBottom();

		let assistantMessage: Message = {
			role: 'assistant',
			content: '',
			timestamp: Date.now(),
			status: 'pending'
		};
		void ensureMarkdownRenderer();
		messages = [...messages, assistantMessage];
		announcement = 'Generating a response.';

		try {
			const url = chatStreamUrl(includePipelineForSession);
			const res = await fetch(url, {
				...chatFetchRequest(userMessage, url),
				signal: controller.signal
			});

			if (generation !== requestGeneration) return;

			if (!res.ok) {
				throw new Error(await parseApiError(res));
			}

			const reader = res.body?.getReader();
			if (!reader) {
				throw new Error('No response body');
			}

			const stream = new SseDecoder();
			let terminal: 'complete' | 'error' | null = null;
			let malformed = false;

			const applyFrames = async (frames: string[]): Promise<void> => {
				for (const dataStr of frames) {
					if (generation !== requestGeneration) return;
					let data: Record<string, unknown>;
					try {
						const parsed = JSON.parse(dataStr);
						if (!parsed || typeof parsed !== 'object') {
							malformed = true;
							continue;
						}
						data = parsed as Record<string, unknown>;
					} catch {
						malformed = true;
						console.error('Failed to parse SSE data frame');
						continue;
					}
					if (typeof data.content === 'string') {
						assistantMessage.content += data.content;
					}
					if (data.done === true) {
						if (data.sources) assistantMessage.sources = data.sources as Message['sources'];
						if (data.pipeline) {
							assistantMessage.pipeline = data.pipeline as PipelineTraceType;
						}
						if (data.error) {
							terminal = 'error';
							assistantMessage.status = 'error';
							const code = data.error_code ? `[${data.error_code}] ` : '';
							const req = data.request_id ? ` (request ${data.request_id})` : '';
							error = `${code}${String(data.error)}${req}`;
							announcement = 'Response failed.';
						} else {
							terminal = 'complete';
							assistantMessage.status = 'complete';
							announcement = 'Response complete.';
						}
					}
					messages = [...messages.slice(0, -1), { ...assistantMessage }];
					await tick();
					if (autoFollow) scrollToBottom();
				}
			};

			while (true) {
				const { done, value } = await reader.read();
				if (done) break;
				if (generation !== requestGeneration) return;
				await applyFrames(stream.push(value));
			}
			await applyFrames(stream.finish());
			if (generation !== requestGeneration) return;

			if (terminal === null) {
				assistantMessage.status = 'incomplete';
				announcement = 'Response incomplete; the stream ended without a completion event.';
				if (malformed) {
					error = 'The response stream contained malformed events; partial output is retained.';
				}
				messages = [...messages.slice(0, -1), { ...assistantMessage }];
			}
		} catch (e) {
			if (generation !== requestGeneration) return;
			if (controller.signal.aborted) {
				assistantMessage.status = 'incomplete';
				announcement = 'Response stopped; partial output retained.';
				messages = [...messages.slice(0, -1), { ...assistantMessage }];
				return;
			}
			assistantMessage.status = 'error';
			error = e instanceof Error ? e.message : 'Failed to send message.';
			announcement = 'Response failed.';
			messages = [...messages.slice(0, -1), { ...assistantMessage }];
			console.error(e);
		} finally {
			if (activeStreamController === controller) {
				activeStreamController = null;
			}
			if (generation === requestGeneration) {
				loading = false;
			}
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.isComposing || e.keyCode === 229) return;
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			sendMessage();
		}
	}

	function statusLabel(status: MessageStatus | undefined): string {
		if (!status) return 'Recorded';
		return status.charAt(0).toUpperCase() + status.slice(1);
	}

	function turnNumber(index: number): number {
		let count = 0;
		for (let position = 0; position <= index; position += 1) {
			if (messages[position]?.role === 'assistant') count += 1;
		}
		return count;
	}

	function inspectTurn(index: number) {
		inspectedIndex = index;
		showPipeline = true;
		void ensurePipelinePanel();
	}

	function togglePipeline(index: number) {
		const willOpen = !(showPipeline && inspectedIndex === index);
		inspectedIndex = index;
		showPipeline = willOpen;
		if (willOpen) void ensurePipelinePanel();
	}

	function focusTurn(index: number) {
		inspectedIndex = index;
		document.getElementById(`turn-${index}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' });
	}

	async function retryTurn(index: number) {
		const question = messages
			.slice(0, index)
			.reverse()
			.find((message) => message.role === 'user')?.content;
		if (!question || loading) return;
		input = question;
		await tick();
		await sendMessage();
	}

	function stopResponse() {
		abortActiveStream();
	}

	const turns = $derived(
		messages.flatMap((message, index) => {
			if (message.role !== 'assistant') return [];
			const question =
				messages
					.slice(0, index)
					.reverse()
					.find((candidate) => candidate.role === 'user')?.content ?? 'Recorded turn';
			const number = messages
				.slice(0, index + 1)
				.filter((candidate) => candidate.role === 'assistant').length;
			return [{ index, number, question, status: message.status }];
		})
	);

	function panelPipelineIndex(): number | null {
		if (inspectedIndex !== null && messages[inspectedIndex]?.pipeline) return inspectedIndex;
		for (let index = messages.length - 1; index >= 0; index -= 1) {
			if (messages[index]?.role === 'assistant' && messages[index]?.pipeline) return index;
		}
		return null;
	}

	$effect(() => {
		chat.messages = messages;
	});

	$effect(() => {
		chat.draft = input;
	});

	async function clearChat() {
		const generation = ++requestGeneration;
		abortActiveStream();
		error = '';
		try {
			await clearHistory();
		} catch (e) {
			if (generation !== requestGeneration) return;
			loading = false;
			error = e instanceof Error ? e.message : 'Failed to clear chat history.';
			console.error('Failed to clear history on server:', e);
			return;
		}

		if (generation !== requestGeneration) return;
		messages = [];
		loading = false;
		showPipeline = false;
		inspectedIndex = null;
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
		hydrated = true;
		loadHistory();
		loadHealth();
		return () => {
			requestGeneration += 1;
			abortActiveStream();
		};
	});

	function hasPipeline(message: Message): boolean {
		return message.role === 'assistant' && message.pipeline !== undefined;
	}

	function extractRetrievalConfig(pipeline: PipelineTraceType): Record<string, unknown> | null {
		const steps = pipeline.retrieval?.steps ?? [];
		for (const step of steps) {
			if (step.details?.search_mode !== undefined) {
				return step.details as Record<string, unknown>;
			}
		}
		return null;
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
		if (tab === 'distribution') {
			void ensureSourceDistributionChart();
		}
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

<svelte:head>
	<title>Ask · Fieldnote</title>
</svelte:head>

<AppShell current="/ask">
<div class="chat-container" data-hydrated={hydrated}>
	<aside class="turn-rail" aria-label="Conversation turns">
		<button type="button" class="rail-new" onclick={clearChat}>New conversation</button>

		<div class="rail-heading">
			<p class="rail-eyebrow">This conversation</p>
			<p class="rail-title">Evidence workbench</p>
		</div>

		<div class="rail-turn-heading">
			<span>Turn index</span>
			<span>{turns.length}</span>
		</div>

		{#if turns.length === 0}
			<p class="rail-empty">No turns yet. Start with a public or synthetic question.</p>
		{:else}
			<ol class="rail-turns">
				{#each turns as turn}
					<li>
						<button
							type="button"
							class="rail-turn"
							class:active={inspectedIndex === turn.index}
							onclick={() => focusTurn(turn.index)}
							title={turn.question}
						>
							<span class="rail-turn-number">{String(turn.number).padStart(2, '0')}</span>
							<span class="rail-turn-question">{turn.question}</span>
							<span class="rail-turn-status">{statusLabel(turn.status)}</span>
						</button>
					</li>
				{/each}
			</ol>
		{/if}

		<p class="rail-note">
			History is cookie-bound. No account or saved-conversation library is available. A hard
			reload loses source and trace detail that was not recorded in history.
		</p>
	</aside>

	<div class="chat-main">
		<header class="ask-header">
			<div class="header-left">
				<p class="ask-eyebrow">Q&amp;A / evidence workbench</p>
				<h1>Ask the evidence.</h1>
				<p class="ask-lede">
					Public or synthetic questions only. This is a private research tool, not a clinical
					service.
				</p>
			</div>
			<div class="header-actions">
				<label class="pipeline-toggle">
					<input type="checkbox" bind:checked={includePipelineForSession} />
					<span>Show pipeline details</span>
				</label>
				<button class="new-chat" onclick={clearChat}>New Chat</button>
			</div>
		</header>

		{#if operationalNotice}
			<div class="status-banner">{operationalNotice}</div>
		{/if}

		<div class="messages" bind:this={messagesContainer} onscroll={handleMessagesScroll}>
			{#if messages.length === 0}
				<div class="welcome">
					<p class="eyebrow">Private research workbench</p>
					<h2>Start with a question about the frozen index.</h2>
					<p>
						Ask about the indexed public or synthetic corpus. Answers are generated from
						retrieved chunks and may be incomplete; inspect the recorded trace before relying
						on them.
					</p>
					<ul>
						<li>No clinical advice, diagnosis or suitability claim.</li>
						<li>Inspect sources and the recorded turn before drawing a conclusion.</li>
					</ul>
				</div>
			{/if}

			{#each messages as msg, index}
				{@const renderableSources = getRenderableSources(msg)}
				{@const typeDistribution = buildDistribution(renderableSources, 'sourceType')}
				{@const classDistribution = buildDistribution(renderableSources, 'sourceClass')}
				<div class="message {msg.role}" id={msg.role === 'assistant' ? `turn-${index}` : undefined}>
					<div class="message-header">
						<span class="role-label">{msg.role === 'user' ? 'You' : 'Fieldnote'}</span>
						{#if msg.timestamp}
							<span class="timestamp">{formatTime(msg.timestamp)}</span>
						{/if}
						{#if msg.role === 'assistant'}
							<span class="turn-status {msg.status ?? 'recorded'}">
								{statusLabel(msg.status)}
							</span>
						{/if}
						{#if msg.role === 'assistant'}
							<button
								class="copy-btn"
								onclick={() => copyMessage(msg.content, index)}
								title="Copy message"
								aria-label={copiedIndex === index
									? `Copied turn ${turnNumber(index)} response`
									: `Copy turn ${turnNumber(index)} response`}
							>
								{copiedIndex === index ? '✓ Copied' : 'Copy'}
							</button>
						{/if}
					</div>
					<div class="content">
						{#if msg.role === 'assistant'}
							{#if MarkdownRendererComponent}
								{@const MarkdownRenderer = MarkdownRendererComponent}
								<MarkdownRenderer content={msg.content} />
							{:else}
								{msg.content}
							{/if}
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
											{#if SourceDistributionChartComponent}
												{@const SourceDistributionChart = SourceDistributionChartComponent}
												<SourceDistributionChart distribution={typeDistribution} title="Source Types" height={180} />
											{/if}
										</div>
									{/if}
									{#if Object.keys(classDistribution).length > 0}
										<div class="distribution-card">
											{#if SourceDistributionChartComponent}
												{@const SourceDistributionChart = SourceDistributionChartComponent}
												<SourceDistributionChart distribution={classDistribution} title="Source Classes" height={180} />
											{/if}
										</div>
									{/if}
									{#if Object.keys(typeDistribution).length === 0 && Object.keys(classDistribution).length === 0}
										<p class="distribution-empty">No structured source distribution available yet.</p>
									{/if}
								</div>
							{/if}
						</div>
					{/if}
					{#if msg.role === 'assistant'}
						<div class="turn-summary">
							<span>
								{renderableSources.length}
								{renderableSources.length === 1 ? 'source entry' : 'source entries'}
							</span>
							<span>{msg.pipeline ? 'Recorded trace available' : 'No breakdown recorded'}</span>
							{#if msg.pipeline}
								<button type="button" class="inspect-turn" onclick={() => inspectTurn(index)}>
									Inspect turn {turnNumber(index)}
								</button>
							{/if}
							{#if msg.status === 'incomplete' || msg.status === 'error'}
								<button
									type="button"
									class="retry-turn"
									onclick={() => retryTurn(index)}
									aria-label={`Ask again for turn ${turnNumber(index)}`}
								>
									Ask again
								</button>
							{/if}
						</div>
					{/if}
					{#if hasPipeline(msg)}
						<button
							class="pipeline-btn"
							class:active={showPipeline && inspectedIndex === index}
							onclick={() => togglePipeline(index)}
						>
							{showPipeline && inspectedIndex === index ? 'Hide' : 'Show'} recorded trace
						</button>
						{@const retrievalCfg = extractRetrievalConfig(msg.pipeline!)}
						{#if retrievalCfg}
							<div class="config-chips">
								{#if typeof retrievalCfg.search_mode === 'string'}
									<span class="chip">{retrievalCfg.search_mode.replace(/_/g, ' ')}</span>
								{/if}
								{#if retrievalCfg.enable_diversification === true}
									<span class="chip">diversified</span>
								{/if}
								{#if retrievalCfg.enable_hyde === true}
									<span class="chip accent">HyDE</span>
								{/if}
								{#if retrievalCfg.enable_reranking === true}
									<span class="chip accent">reranked</span>
								{/if}
								{#if typeof retrievalCfg.top_k === 'number'}
									<span class="chip">top-{retrievalCfg.top_k}</span>
								{/if}
							</div>
						{/if}
					{/if}
				</div>
			{/each}

			{#if !autoFollow && messages.length > 0}
				<button type="button" class="jump-latest" onclick={scrollToBottom}>Jump to latest</button>
			{/if}

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
			<label class="sr-only" for="ask-input">Question</label>
			<textarea
				id="ask-input"
				bind:value={input}
				onkeydown={handleKeydown}
				placeholder="Ask a question..."
				rows="2"
				maxlength={MAX_MESSAGE_LENGTH}
				disabled={loading}
				aria-describedby="ask-composer-help"
			></textarea>
			{#if loading}
				<button type="button" class="stop-button" onclick={stopResponse}>Stop response</button>
			{:else}
				<button onclick={sendMessage} disabled={!input.trim() || input.trim().length > MAX_MESSAGE_LENGTH}>
					Send
				</button>
			{/if}
			<div class="composer-help" id="ask-composer-help">
				<span>{input.length.toLocaleString()} / {MAX_MESSAGE_LENGTH.toLocaleString()} characters</span>
				<span>Enter sends; Shift+Enter adds a line. Do not enter identifying information.</span>
			</div>
		</div>
		<p class="sr-only" aria-live="polite">{announcement}</p>
	</div>

	{#if showPipeline && PipelinePanelComponent}
		{@const selectedIndex = panelPipelineIndex()}
		{#if selectedIndex !== null && messages[selectedIndex]?.pipeline}
			{@const PipelinePanel = PipelinePanelComponent}
			<PipelinePanel
				pipeline={messages[selectedIndex].pipeline!}
				bind:isOpen={showPipeline}
			/>
		{/if}
	{/if}
</div>
</AppShell>

<style>
	.chat-container {
		display: grid;
		grid-template-columns: 240px minmax(0, 1fr);
		align-items: start;
		gap: 1.25rem;
		width: 100%;
		min-height: calc(100vh - 8rem);
	}

	.turn-rail {
		position: sticky;
		top: 1rem;
		display: flex;
		flex-direction: column;
		gap: 1.15rem;
		min-height: 560px;
		padding: 1.1rem;
		border-radius: 14px;
		background: var(--ink);
		color: var(--paper);
	}

	.rail-new {
		min-height: 44px;
		padding: 0.55rem 0.75rem;
		border: 1px solid rgba(247, 244, 237, 0.24);
		border-radius: 7px;
		background: var(--paper);
		color: var(--ink);
		font-weight: 700;
		cursor: pointer;
	}

	.rail-heading {
		display: grid;
		gap: 0.3rem;
	}

	.rail-eyebrow,
	.rail-turn-heading,
	.ask-eyebrow,
	.eyebrow {
		margin: 0;
		font-size: 0.68rem;
		font-weight: 700;
		letter-spacing: 0.14em;
		text-transform: uppercase;
	}

	.rail-eyebrow,
	.rail-turn-heading {
		color: #b9cbc7;
	}

	.rail-title {
		margin: 0;
		font-family: var(--font-heading);
		font-size: 1.3rem;
		line-height: 1.15;
	}

	.rail-turn-heading {
		display: flex;
		justify-content: space-between;
		gap: 0.5rem;
		padding-top: 0.15rem;
	}

	.rail-empty {
		margin: 0;
		color: #b9cbc7;
		font-size: 0.78rem;
		line-height: 1.45;
	}

	.rail-turns {
		display: grid;
		gap: 0.35rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.rail-turn {
		display: grid;
		grid-template-columns: 1.5rem minmax(0, 1fr);
		gap: 0.15rem 0.5rem;
		width: 100%;
		min-height: 44px;
		padding: 0.5rem;
		border: 1px solid transparent;
		border-radius: 6px;
		background: transparent;
		color: #dce7e4;
		font: inherit;
		font-size: 0.78rem;
		text-align: left;
		cursor: pointer;
	}

	.rail-turn:hover {
		background: rgba(247, 244, 237, 0.08);
	}

	.rail-turn.active {
		border-color: rgba(247, 244, 237, 0.2);
		background: var(--teal);
		color: white;
	}

	.rail-turn-number {
		font-variant-numeric: tabular-nums;
		font-weight: 700;
		color: #b9cbc7;
	}

	.rail-turn.active .rail-turn-number {
		color: #d9ece8;
	}

	.rail-turn-question {
		display: -webkit-box;
		overflow: hidden;
		line-height: 1.35;
		-webkit-box-orient: vertical;
		line-clamp: 2;
		-webkit-line-clamp: 2;
	}

	.rail-turn-status {
		grid-column: 2;
		font-size: 0.64rem;
		font-weight: 700;
		letter-spacing: 0.08em;
		text-transform: uppercase;
		color: #9fc7bf;
	}

	.rail-turn.active .rail-turn-status {
		color: #d9ece8;
	}

	.rail-note {
		margin-top: auto;
		color: #b9cbc7;
		font-size: 0.72rem;
		line-height: 1.45;
	}

	.chat-main {
		display: flex;
		flex-direction: column;
		gap: 1rem;
		min-width: 0;
	}

	.ask-header {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		flex-wrap: wrap;
		gap: 1rem;
		margin-bottom: 0.25rem;
	}

	.ask-eyebrow,
	.eyebrow {
		color: var(--muted-color);
	}

	.header-left {
		display: flex;
		flex-direction: column;
		gap: 0.35rem;
		max-width: 48rem;
	}

	.ask-header h1 {
		margin: 0;
		font-size: 2.8rem;
		line-height: 1.05;
	}

	.ask-lede {
		margin: 0;
		max-width: 55ch;
		color: var(--muted-color);
		font-size: 1rem;
	}

	.header-actions {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: flex-end;
		gap: 0.65rem;
	}

	.pipeline-toggle {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		min-height: 44px;
		color: var(--muted-color);
		font-size: 0.82rem;
		cursor: pointer;
		user-select: none;
	}

	.pipeline-toggle input[type='checkbox'] {
		width: 18px;
		height: 18px;
		cursor: pointer;
	}

	.new-chat {
		min-height: 44px;
		padding: 0.55rem 0.95rem;
		border: 1px solid var(--border-color);
		border-radius: 999px;
		background: #fffdf8;
		color: var(--ink);
		font-weight: 700;
		cursor: pointer;
	}

	.new-chat:hover {
		border-color: var(--teal);
	}

	.messages {
		flex: 1;
		min-height: 420px;
		max-height: 62vh;
		overflow-y: auto;
		padding: 1.25rem;
		border: 1px solid var(--border-color);
		border-radius: 14px;
		background: #fffdf8;
	}

	.welcome {
		max-width: 54ch;
		margin: 1.5rem auto;
		padding: 1.25rem 1.5rem;
		border-left: 3px solid var(--teal);
		background: var(--surface-subtle);
		color: var(--secondary);
	}

	.welcome .eyebrow {
		margin-bottom: 0.5rem;
	}

	.welcome h2 {
		margin: 0 0 0.65rem;
		font-size: 1.8rem;
		line-height: 1.15;
		color: var(--ink);
	}

	.welcome p {
		margin: 0;
		line-height: 1.55;
	}

	.welcome ul {
		display: grid;
		gap: 0.3rem;
		margin: 0.9rem 0 0;
		padding-left: 1.1rem;
		font-size: 0.86rem;
	}

	.message {
		width: 100%;
		margin-bottom: 1rem;
		padding: 1rem 0;
		border-radius: 8px;
	}

	.message.user {
		padding: 0.75rem 1rem;
		border-left: 3px solid var(--blue);
		background: var(--surface-subtle);
	}

	.message.assistant {
		padding: 1rem;
		border: 1px solid var(--border-color);
		background: white;
	}

	.message.loading {
		border: 1px solid var(--border-color);
		background: white;
		opacity: 0.7;
	}

	.turn-status {
		display: inline-flex;
		align-items: center;
		padding: 0.15rem 0.45rem;
		border: 1px solid var(--border-color);
		border-radius: 999px;
		color: var(--muted-color);
		font-size: 0.66rem;
		font-weight: 700;
		letter-spacing: 0.05em;
		text-transform: uppercase;
	}

	.turn-status.complete {
		border-color: var(--teal);
		color: var(--teal);
	}

	.turn-status.pending {
		border-color: var(--blue);
		color: var(--blue);
	}

	.turn-status.incomplete,
	.turn-status.error {
		border-color: var(--rust);
		color: var(--rust);
	}

	.turn-summary {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		gap: 0.6rem;
		margin-top: 0.85rem;
		padding: 0.65rem 0.75rem;
		border-left: 3px solid var(--teal);
		background: var(--surface-subtle);
		color: var(--secondary);
		font-size: 0.76rem;
	}

	.inspect-turn,
	.retry-turn {
		min-height: 36px;
		padding: 0.2rem 0.6rem;
		border: 1px solid var(--border-color);
		border-radius: 4px;
		background: transparent;
		color: var(--teal);
		font: inherit;
		font-size: 0.76rem;
		font-weight: 700;
		cursor: pointer;
	}

	.inspect-turn {
		margin-left: auto;
	}

	.retry-turn {
		color: var(--rust);
	}

	.jump-latest {
		align-self: flex-end;
		margin: 0.25rem 0;
		padding: 0.35rem 0.65rem;
		border: 1px solid var(--border-color);
		border-radius: 999px;
		background: #fffdf8;
		color: var(--teal);
		font: inherit;
		font-size: 0.78rem;
		font-weight: 700;
		cursor: pointer;
	}

	.sr-only {
		position: absolute;
		width: 1px;
		height: 1px;
		padding: 0;
		margin: -1px;
		overflow: hidden;
		clip: rect(0, 0, 0, 0);
		white-space: nowrap;
		border: 0;
	}

	.message-header {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		margin-bottom: 0.55rem;
		font-size: 0.78rem;
	}

	.role-label {
		font-weight: 700;
		color: var(--ink);
	}

	.timestamp {
		color: var(--muted-color);
	}

	.copy-btn {
		margin-left: auto;
		padding: 0.2rem 0.5rem;
		border: 1px solid var(--border-color);
		border-radius: 3px;
		background: transparent;
		color: var(--muted-color);
		font-size: 0.72rem;
		cursor: pointer;
	}

	.copy-btn:hover {
		background: var(--surface-subtle);
	}

	.typing-indicator {
		display: flex;
		gap: 4px;
		padding: 0.5rem;
	}

	.typing-indicator span {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--teal);
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
		0%,
		60%,
		100% {
			transform: translateY(0);
			opacity: 0.4;
		}
		30% {
			transform: translateY(-6px);
			opacity: 1;
		}
	}

	.content {
		max-width: 76ch;
		white-space: pre-wrap;
		line-height: 1.55;
	}

	.message.user .content {
		max-width: 80ch;
	}

	.content :global(code) {
		padding: 0.1rem 0.3rem;
		border-radius: 3px;
		background: var(--surface-subtle);
		font-family: monospace;
		font-size: 0.9em;
	}

	.content :global(strong) {
		font-weight: 600;
	}

	.sources-panel {
		display: grid;
		gap: 0.55rem;
		margin-top: 0.75rem;
		padding: 0.75rem;
		border: 1px solid var(--border-color);
		border-radius: 10px;
		background: var(--surface-subtle);
		color: var(--secondary);
		font-size: 0.84rem;
	}

	.sources-panel-header {
		display: flex;
		flex-wrap: wrap;
		align-items: center;
		justify-content: space-between;
		gap: 0.75rem;
	}

	.source-tabs {
		display: flex;
		flex-wrap: wrap;
		gap: 0.4rem;
	}

	.source-tabs button {
		padding: 0.35rem 0.7rem;
		border: 1px solid var(--border-color);
		border-radius: 999px;
		background: #fffdf8;
		color: var(--secondary);
		font-size: 0.75rem;
		cursor: pointer;
	}

	.source-tabs button.active {
		border-color: var(--teal);
		background: var(--teal);
		color: white;
	}

	.sources-list {
		display: grid;
		gap: 0.45rem;
		margin: 0;
		padding: 0;
		list-style: none;
	}

	.source-card {
		display: grid;
		gap: 0.55rem;
		padding: 0.75rem;
		border: 1px solid var(--border-color);
		border-radius: 8px;
		background: #fffdf8;
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
		font-weight: 700;
		color: var(--muted-color);
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
		font-size: 0.7rem;
		font-weight: 600;
	}

	.source-type-pill {
		background: #e4e9f2;
		color: var(--blue);
	}

	.source-class-pill {
		background: #dceee8;
		color: var(--teal);
	}

	.source-meta-pill {
		background: #f3e5dc;
		color: var(--rust);
	}

	.source-link,
	.source-text {
		color: var(--ink);
		font-size: 0.92rem;
		word-break: break-word;
	}

	.source-link {
		text-decoration: none;
	}

	.source-link:hover {
		text-decoration: underline;
	}

	.source-domain {
		color: var(--muted-color);
		font-size: 0.78rem;
	}

	.distribution-grid {
		display: grid;
		grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
		gap: 0.75rem;
	}

	.distribution-card {
		padding: 0.5rem;
		border: 1px solid var(--border-color);
		border-radius: 8px;
		background: #fffdf8;
	}

	.distribution-empty {
		margin: 0;
		color: var(--muted-color);
		font-size: 0.9rem;
	}

	.pipeline-btn {
		margin-top: 0.65rem;
		padding: 0.35rem 0;
		border: none;
		background: transparent;
		color: var(--teal);
		font: inherit;
		font-size: 0.78rem;
		font-weight: 700;
		text-decoration: underline;
		text-underline-offset: 3px;
		cursor: pointer;
	}

	.config-chips {
		display: flex;
		flex-wrap: wrap;
		gap: 0.35rem;
		margin-top: 0.5rem;
	}

	.chip {
		padding: 0.15rem 0.5rem;
		border-radius: 999px;
		background: var(--surface-subtle);
		color: var(--secondary);
		font-size: 0.7rem;
		font-weight: 600;
	}

	.chip.accent {
		background: #dceee8;
		color: var(--teal);
	}

	.error {
		padding: 0.65rem 0.75rem;
		border-left: 3px solid var(--rust);
		background: #f8e8e1;
		color: #7f2d15;
		font-size: 0.86rem;
	}

	.status-banner {
		padding: 0.85rem 1rem;
		border: 1px solid #e7c67e;
		border-radius: 10px;
		background: #fff7e6;
		color: #6b4200;
		font-size: 0.9rem;
	}

	.input-area {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
		padding: 1rem;
		border: 1px solid var(--border-color);
		border-radius: 14px;
		background: #fffdf8;
	}

	.input-area textarea {
		flex: 1 1 240px;
		min-width: 0;
		padding: 0.75rem;
		border: 1px solid var(--border-color);
		border-radius: 8px;
		background: var(--surface-subtle);
		font-family: inherit;
		font-size: 1rem;
		resize: none;
	}

	.input-area textarea:focus {
		border-color: var(--teal);
	}

	.input-area button {
		min-height: 44px;
		padding: 0.75rem 1.5rem;
		border: none;
		border-radius: 999px;
		background: var(--teal);
		color: white;
		font-weight: 700;
		cursor: pointer;
	}

	.input-area button:hover:not(:disabled) {
		background: #00544c;
	}

	.input-area button:disabled {
		background: #c8c3b8;
		cursor: not-allowed;
	}

	.input-area .stop-button {
		background: var(--rust);
	}

	.input-area .stop-button:hover {
		background: #8f351b;
	}

	.composer-help {
		display: flex;
		flex-wrap: wrap;
		justify-content: space-between;
		gap: 0.35rem 0.75rem;
		width: 100%;
		color: var(--muted-color);
		font-size: 0.72rem;
	}

	@media (max-width: 1024px) {
		.chat-container {
			grid-template-columns: minmax(0, 1fr);
		}

		.turn-rail {
			display: none;
		}
	}

	@media (max-width: 640px) {
		.ask-header h1 {
			font-size: 2.1rem;
		}

		.header-actions {
			justify-content: flex-start;
		}

		.messages {
			min-height: 320px;
			max-height: none;
			padding: 1rem;
		}

		.welcome {
			margin: 0.5rem auto;
			padding: 1rem;
		}

		.welcome h2 {
			font-size: 1.45rem;
		}

		.inspect-turn {
			margin-left: 0;
		}

		.timestamp {
			display: none;
		}
	}

	@media (max-width: 480px) {
		.input-area {
			display: grid;
			grid-template-columns: minmax(0, 1fr);
		}

		.input-area button {
			width: 100%;
		}
	}

	@media (prefers-reduced-motion: reduce) {
		.typing-indicator span {
			animation: none;
		}
	}
</style>
