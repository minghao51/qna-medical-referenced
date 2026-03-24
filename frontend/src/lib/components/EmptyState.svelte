<script lang="ts">
	type Props = {
		title: string;
		body?: string;
	};

	let { title, body }: Props = $props();
</script>

<div class="empty-state">
	<h3>{title}</h3>
	{#if body}
		<p>{body}</p>
	{/if}
</div>

<style>
	.empty-state {
		padding: 2rem 1.25rem;
		border: 1px dashed var(--border-color);
		border-radius: 16px;
		background: var(--surface-subtle);
		text-align: center;
	}

	h3 {
		margin: 0;
		font-size: 1rem;
	}

	p {
		margin: 0.5rem 0 0;
		color: var(--muted-color);
	}
</style>
