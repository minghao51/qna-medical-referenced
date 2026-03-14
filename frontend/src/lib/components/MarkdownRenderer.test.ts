import { render } from '@testing-library/svelte';
import { describe, it, expect } from 'vitest';
import MarkdownRenderer from './MarkdownRenderer.svelte';

describe('MarkdownRenderer', () => {
  it('should render markdown content', async () => {
    const { container } = render(MarkdownRenderer, {
      props: { content: '# Test Heading' }
    });
    expect(container.querySelector('h1')).toBeTruthy();
    expect(container.querySelector('h1')?.textContent).toBe('Test Heading');
  });

  it('should render bold text', async () => {
    const { container } = render(MarkdownRenderer, {
      props: { content: '**bold text**' }
    });
    expect(container.querySelector('strong')?.textContent).toBe('bold text');
  });

  it('should render code blocks', async () => {
    const { container } = render(MarkdownRenderer, {
      props: { content: '```python\nprint("hello")\n```' }
    });
    const pre = container.querySelector('pre code');
    expect(pre).toBeTruthy();
    expect(pre?.classList.contains('hljs')).toBe(true);
  });

  it('should sanitize XSS attempts', async () => {
    const { container } = render(MarkdownRenderer, {
      props: { content: '<script>alert("xss")</script>' }
    });
    expect(container.querySelector('script')).toBeFalsy();
  });

  it('should render tables', async () => {
    const { container } = render(MarkdownRenderer, {
      props: { content: '| H1 | H2 |\n|-----|-----|\n| C1 | C2 |' }
    });
    expect(container.querySelector('table')).toBeTruthy();
    expect(container.querySelector('th')?.textContent).toBe('H1');
  });

  it('should render lists', async () => {
    const { container } = render(MarkdownRenderer, {
      props: { content: '- Item 1\n- Item 2' }
    });
    const list = container.querySelector('ul');
    expect(list).toBeTruthy();
    expect(list?.querySelectorAll('li').length).toBe(2);
  });
});
