<script lang="ts">
	export let href = '';
	export let title: string | undefined = undefined;

	$: isAnchorLink = href.startsWith('#');
	$: isRelativeLink = href.startsWith('/');
	$: isSafeAbsoluteLink = /^https?:\/\//i.test(href);
	$: isSafeLink = isAnchorLink || isRelativeLink || isSafeAbsoluteLink;
	$: openInNewTab = isSafeAbsoluteLink;
</script>

{#if isSafeLink}
	<a
		href={href}
		{title}
		target={openInNewTab ? '_blank' : undefined}
		rel={openInNewTab ? 'noopener noreferrer' : undefined}
	>
		<slot />
	</a>
{:else}
	<span class="md-link-literal"><slot /></span>
{/if}
