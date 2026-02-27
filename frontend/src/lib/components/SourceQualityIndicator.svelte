<script lang="ts">
	import { getDomainType, type DomainType } from '$lib/confidenceCalculator';

	type Props = {
		source: string;
	};

	let { source }: Props = $props();

	const domainType = $derived(getDomainType(source));

	const config: Record<DomainType, { color: string; bgColor: string; label: string }> = {
		government: {
			color: '#1d4ed8',
			bgColor: '#dbeafe',
			label: 'Official'
		},
		education: {
			color: '#7c3aed',
			bgColor: '#ede9fe',
			label: 'Education'
		},
		organization: {
			color: '#059669',
			bgColor: '#d1fae5',
			label: 'Organization'
		},
		commercial: {
			color: '#6b7280',
			bgColor: '#f3f4f6',
			label: 'General'
		},
		unknown: {
			color: '#6b7280',
			bgColor: '#f3f4f6',
			label: 'Unknown'
		}
	};

	const currentConfig = $derived(config[domainType]);
</script>

{#if source}
	<span
		class="source-badge"
		style="--badge-color: {currentConfig.color}; --badge-bg: {currentConfig.bgColor};"
		title="Source type: {domainType}"
	>
		{currentConfig.label}
	</span>
{/if}

<style>
	.source-badge {
		display: inline-block;
		padding: 0.15rem 0.4rem;
		border-radius: 3px;
		font-size: 0.7rem;
		font-weight: 600;
		background: var(--badge-bg);
		color: var(--badge-color);
		white-space: nowrap;
		text-transform: uppercase;
		letter-spacing: 0.02em;
	}
</style>
