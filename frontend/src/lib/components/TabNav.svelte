<script lang="ts">
	interface Tab {
		id: string;
		label: string;
		icon?: string;
	}

	interface Props {
		tabs: Tab[];
		activeTab: string;
		onchange: (tabId: string) => void;
		label?: string;
	}

	let { tabs, activeTab, onchange, label = 'Sections' }: Props = $props();

	function handleKeydown(event: KeyboardEvent, index: number) {
		if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft' && event.key !== 'Home' && event.key !== 'End') {
			return;
		}

		event.preventDefault();

		let nextIndex = index;
		if (event.key === 'ArrowRight') nextIndex = (index + 1) % tabs.length;
		if (event.key === 'ArrowLeft') nextIndex = (index - 1 + tabs.length) % tabs.length;
		if (event.key === 'Home') nextIndex = 0;
		if (event.key === 'End') nextIndex = tabs.length - 1;

		onchange(tabs[nextIndex].id);
		const nextButton = document.getElementById(`tab-${tabs[nextIndex].id}`);
		nextButton?.focus();
	}
</script>

<div class="tab-nav" role="tablist" aria-label={label}>
	{#each tabs as tab, index}
		<button
			id={`tab-${tab.id}`}
			role="tab"
			aria-selected={activeTab === tab.id}
			aria-controls={`panel-${tab.id}`}
			tabindex={activeTab === tab.id ? 0 : -1}
			class="tab-button"
			class:active={activeTab === tab.id}
			onclick={() => onchange(tab.id)}
			onkeydown={(event) => handleKeydown(event, index)}
		>
			{#if tab.icon}
				<span class="tab-icon">{tab.icon}</span>
			{/if}
			<span class="tab-label">{tab.label}</span>
		</button>
	{/each}
</div>

<style>
	.tab-nav {
		display: flex;
		gap: 0.25rem;
		background: #f8f9fa;
		padding: 0.25rem;
		border-radius: 8px;
		overflow-x: auto;
		-webkit-overflow-scrolling: touch;
		scrollbar-width: none;
	}

	.tab-nav::-webkit-scrollbar {
		display: none;
	}

	.tab-button {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.6rem 1rem;
		border: none;
		background: transparent;
		border-radius: 6px;
		cursor: pointer;
		font-size: 0.9rem;
		font-weight: 500;
		color: #666;
		white-space: nowrap;
		transition: all 0.2s ease;
	}

	.tab-button:hover:not(.active) {
		background: rgba(0, 0, 0, 0.05);
		color: #333;
	}

	.tab-button.active {
		background: white;
		color: #1976d2;
		box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
	}

	.tab-icon {
		font-size: 1rem;
	}

	.tab-label {
		font-weight: 600;
	}

	@media (max-width: 600px) {
		.tab-button {
			padding: 0.5rem 0.75rem;
			font-size: 0.85rem;
		}

		.tab-label {
			font-weight: 500;
		}
	}
</style>
