<script lang="ts">
	import { getDomainType, type DomainType } from '$lib/confidenceCalculator';

	type Props = {
		source?: string | null;
		sourceType?: string | null;
		domainType?: DomainType | null;
	};

	let { source = null, sourceType = null, domainType = null }: Props = $props();

	const resolvedDomainType = $derived(
		domainType ??
			(sourceType === 'pdf' || sourceType === 'html' || sourceType === 'reference_csv'
				? 'organization'
				: getDomainType(source ?? ''))
	);

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

	const currentConfig = $derived(config[resolvedDomainType]);
</script>

{#if source || sourceType || domainType}
	<span
		class="source-badge"
		style="--badge-color: {currentConfig.color}; --badge-bg: {currentConfig.bgColor};"
		title="Source type: {resolvedDomainType}"
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
