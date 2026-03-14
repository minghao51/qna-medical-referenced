<script lang="ts">
  import SvelteMarkdown from 'svelte-markdown';
  import hljs from 'highlight.js/lib/core';
  import python from 'highlight.js/lib/languages/python';
  import javascript from 'highlight.js/lib/languages/javascript';
  import typescript from 'highlight.js/lib/languages/typescript';
  import bash from 'highlight.js/lib/languages/bash';
  import json from 'highlight.js/lib/languages/json';
  import xml from 'highlight.js/lib/languages/xml';
  import plaintext from 'highlight.js/lib/languages/plaintext';

  // Register languages for tree-shaking
  hljs.registerLanguage('python', python);
  hljs.registerLanguage('javascript', javascript);
  hljs.registerLanguage('typescript', typescript);
  hljs.registerLanguage('bash', bash);
  hljs.registerLanguage('json', json);
  hljs.registerLanguage('xml', xml);
  hljs.registerLanguage('plaintext', plaintext);

  interface Props {
    content: string;
    className?: string;
    maxHeight?: string;
    showCopyButton?: boolean;
    codeTheme?: 'light' | 'dark' | 'github';
    truncate?: number;
    onError?: (error: Error) => void;
  }

  let {
    content,
    className = '',
    maxHeight,
    showCopyButton = true,
    codeTheme = 'github',
    truncate,
    onError = console.error
  }: Props = $props();

  let copiedCode = $state<string | null>(null);
  let codeBlockId = $state(0);

  // Truncate content if needed
  let displayContent = $derived(truncate && content.length > truncate
    ? content.slice(0, truncate) + '...'
    : content
  );

  async function copyToClipboard(code: string, id: string) {
    try {
      await navigator.clipboard.writeText(code);
      copiedCode = id;
      setTimeout(() => copiedCode = null, 2000);
    } catch (err) {
      onError(err as Error);
    }
  }
</script>

<div class="markdown-renderer {className}" style:max-height={maxHeight}>
  {#if content && typeof content === 'string'}
    <SvelteMarkdown source={displayContent} />
  {:else}
    <p class="error">Unable to display content</p>
  {/if}
</div>

<style>
  .error {
    color: #d32f2f;
    font-style: italic;
  }

  :global(.code-copy-button) {
    position: absolute;
    top: 8px;
    right: 8px;
    min-width: 44px;
    min-height: 44px;
    padding: 8px 12px;
    background-color: rgba(0, 0, 0, 0.7);
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 14px;
    z-index: 10;
  }

  :global(.code-copy-button:hover) {
    background-color: rgba(0, 0, 0, 0.85);
  }
</style>
