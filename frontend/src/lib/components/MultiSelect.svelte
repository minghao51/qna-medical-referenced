<script lang="ts">
	type Props = {
		options: string[];
		value?: string[];
		label?: string;
	};

	let { options, value = $bindable([]), label }: Props = $props();

	let isOpen = $state(false);

	function toggle(option: string) {
		if (value.includes(option)) {
			const idx = value.indexOf(option);
			value.splice(idx, 1);
		} else {
			value.push(option);
		}
		// Trigger reactivity
		value = [...value];
	}

	function toggleDropdown() {
		isOpen = !isOpen;
	}

	function closeDropdown() {
		isOpen = false;
	}

	const displayText = $derived(
		value.length === options.length ? 'All' : value.length === 0 ? 'None' : `${value.length} selected`
	);
</script>

<div class="multiselect">
	{#if label}
		<span class="multiselect-label">{label}</span>
	{/if}
	<button
		type="button"
		class="multiselect-trigger"
		aria-expanded={isOpen}
		onclick={toggleDropdown}
		onblur={closeDropdown}
	>
		<span class="multiselect-text">{displayText}</span>
		<span class="multiselect-arrow" class:open={isOpen}>▼</span>
	</button>
	{#if isOpen}
		<div class="multiselect-options">
			{#each options as option}
				<button
					type="button"
					class="multiselect-option"
					class:selected={value.includes(option)}
					onclick={(e) => {
						e.stopPropagation();
						toggle(option);
					}}
				>
					<span class="checkbox">{value.includes(option) ? '☑' : '☐'}</span>
					<span>{option}</span>
				</button>
			{/each}
		</div>
	{/if}
</div>

<style>
	.multiselect {
		position: relative;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
	}

	.multiselect-label {
		font-size: 0.85rem;
		color: #666;
		font-weight: 500;
	}

	.multiselect-trigger {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: 0.4rem 0.75rem;
		border: 1px solid #ddd;
		border-radius: 4px;
		background: white;
		cursor: pointer;
		user-select: none;
		min-width: 150px;
		width: 100%;
	}

	.multiselect-trigger:hover {
		border-color: #2196f3;
	}

	.multiselect-text {
		font-size: 0.9rem;
		color: #333;
	}

	.multiselect-arrow {
		font-size: 0.7rem;
		color: #666;
		transition: transform 0.2s;
	}

	.multiselect-arrow.open {
		transform: rotate(180deg);
	}

	.multiselect-options {
		position: absolute;
		top: 100%;
		left: 0;
		right: 0;
		margin-top: 0.25rem;
		background: white;
		border: 1px solid #ddd;
		border-radius: 4px;
		box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
		z-index: 1000;
		max-height: 250px;
		overflow-y: auto;
	}

	.multiselect-option {
		display: flex;
		align-items: center;
		gap: 0.5rem;
		padding: 0.5rem 0.75rem;
		border: none;
		background: white;
		width: 100%;
		cursor: pointer;
		transition: background 0.15s;
		text-align: left;
	}

	.multiselect-option:hover {
		background: #f5f5f5;
	}

	.multiselect-option.selected {
		background: #e3f2fd;
	}

	.checkbox {
		font-size: 1rem;
		color: #666;
	}
</style>
