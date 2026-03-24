<script lang="ts">
	type Props = {
		title: string;
		description?: string;
		children: import('svelte').Snippet;
		actions?: import('svelte').Snippet;
	};

	let { title, description, children, actions }: Props = $props();
</script>

<section class="eval-section section">
	<div class="section-head">
		<div>
			<h3>{title}</h3>
			{#if description}
				<p>{description}</p>
			{/if}
		</div>
		{#if actions}
			<div class="actions">
				{@render actions()}
			</div>
		{/if}
	</div>
	<div class="section-body">
		{@render children()}
	</div>
</section>

<style>
	.eval-section {
		padding: 1.1rem;
		border: 1px solid var(--border-color);
		border-radius: 18px;
		background: white;
	}

	.section-head {
		display: flex;
		align-items: flex-start;
		justify-content: space-between;
		gap: 1rem;
		margin-bottom: 1rem;
	}

	h3 {
		margin: 0;
		font-size: 1.05rem;
	}

	p {
		margin: 0.35rem 0 0;
		font-size: 0.93rem;
		color: var(--muted-color);
	}

	.section-body {
		display: flex;
		flex-direction: column;
		gap: 1rem;
	}

	.actions {
		display: flex;
		flex-wrap: wrap;
		gap: 0.5rem;
	}

	@media (max-width: 720px) {
		.section-head {
			flex-direction: column;
		}
	}
</style>
