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

  export let content: string;
  export let class: string = '';
  export let maxHeight: string | undefined = undefined;
  export let showCopyButton: boolean = true;
  export let codeTheme: 'light' | 'dark' | 'github' = 'github';
  export let truncate: number | undefined = undefined;
  export let onError: (error: Error) => void = console.error;

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

  // Custom renderer for code blocks with syntax highlighting
  const renderers = {
    code: (code: { language: string; text: string }) => {
      const id = `code-block-${codeBlockId++}`;
      const lang = code.language || 'plaintext';
      const highlighted = hljs.highlight(code.text, { language: lang }).value;

      return `
        <div style="position: relative;">
          <button
            class="code-copy-button"
            data-code-id="${id}"
            data-code-text="${encodeURIComponent(code.text)}"
            aria-label="Copy code to clipboard"
          >
            ${copiedCode === id ? 'Copied!' : 'Copy'}
          </button>
          <pre><code class="hljs language-${lang}">${highlighted}</code></pre>
        </div>
      `;
    }
  };

  function handleClick(e: MouseEvent) {
    const button = (e.target as HTMLElement).closest('.code-copy-button');
    if (button) {
      const codeText = decodeURIComponent(button.getAttribute('data-code-text') || '');
      const codeId = button.getAttribute('data-code-id') || '';
      copyToClipboard(codeText, codeId);
    }
  }
</script>

<div class="markdown-renderer {class}" style:max-height={maxHeight} on:click={handleClick}>
  {#if content && typeof content === 'string'}
    <SvelteMarkdown source={displayContent} {renderers} />
  {:else}
    <p class="error">Unable to display content</p>
  {/if}
</div>

<style>
  .code-copy-button {
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

  .code-copy-button:hover {
    background-color: rgba(0, 0, 0, 0.85);
  }

  .error {
    color: #d32f2f;
    font-style: italic;
  }
</style>
