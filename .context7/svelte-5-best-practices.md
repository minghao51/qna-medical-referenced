# Svelte 5 Best Practices & Guidelines

## Overview

This project uses Svelte 5 with the new runes API. This document outlines the best practices to follow when writing or modifying frontend code.

## Core Runes

### `$state` - Reactive State

```svelte
<script>
  let count = $state(0);
  
  // For objects/arrays - can mutate directly
  let items = $state([]);
  items.push(newItem); // Works directly in Svelte 5
</script>
```

### `$derived` - Computed Values

```svelte
<script>
  let count = $state(0);
  let doubled = $derived(count * 2);
</script>
```

### `$props` - Component Properties

```svelte
<script>
  let { title, count = 0, onIncrement } = $props();
</script>
```

### `$bindable` - Two-way Bindings

```svelte
<script>
  let { value = $bindable(0) } = $props();
</script>

<button onclick={() => value++}>{value}</button>
```

### `$effect` - Side Effects

```svelte
<script>
  let count = $state(0);
  
  $effect(() => {
    console.log(`Count is now ${count}`);
    return () => console.log('Cleanup');
  });
</script>
```

## Migration from Svelte 4

| Feature | Svelte 4 | Svelte 5 |
|---------|-----------|----------|
| State | `let count = 0;` | `let count = $state(0);` |
| Derived | `$: doubled = count * 2;` | `let doubled = $derived(count * 2);` |
| Props | `export let title;` | `let { title } = $props();` |
| Lifecycle | `onMount(() => {})` | `$effect(() => {})` |
| Events | `on:click={fn}` | `onclick={fn}` |
| Slots | `<slot />` | `{@render children?.()}` |

## Project-Specific Patterns

### Props Definition Pattern

Always use explicit type annotations:

```svelte
<script lang="ts">
  import type { MyType } from '$lib/types';
  
  let { 
    data, 
    label = 'Default',
    onAction 
  }: { 
    data: MyType; 
    label?: string; 
    onAction?: () => void;
  } = $props();
</script>
```

### Two-way Binding Pattern

For props that need to be mutable from the parent:

```svelte
<script>
  let { isOpen = $bindable(false) } = $props();
</script>

<button onclick={() => isOpen = !isOpen}>Toggle</button>
```

### Children/Slot Pattern

Use `children` prop with `{@render}`:

```svelte
<script>
  let { children } = $props();
</script>

<div>
  {@render children?.()}
</div>
```

Parent usage:
```svelte
<MyComponent>
  <p>Content here</p>
</MyComponent>
```

### Event Handling

Use standard HTML attributes (not Svelte 4 directives):

```svelte
<button onclick={handleClick}>Click me</button>
<input oninput={handleInput} />
```

## Common Issues & Fixes

### Issue: "flip is not a valid transition"

**Problem:** `flip` was a Svelte 4 transition that doesn't exist in Svelte 5.

**Fix:** Remove `|flip` from transitions or implement custom animation.

### Issue: "createEventDispatcher not found"

**Problem:** Svelte 5 uses callback props instead of event dispatchers.

**Fix:** Pass functions directly as props:

```svelte
// Before (Svelte 4)
const dispatch = createEventDispatcher();
dispatch('toggle', { value });

// After (Svelte 5)
let { onToggle } = $props();
onToggle?.({ value });
```

### Issue: "export let" not working

**Problem:** Svelte 5 uses `$props()` instead of `export let`.

**Fix:** 
```svelte
// Before
export let title: string;

// After  
let { title } = $props();
```

## Running the Project

```bash
# Frontend (development)
cd frontend && bun run dev

# Backend
cd src && uv run python -m src.main
```

## References

- [Svelte 5 Migration Guide](https://svelte.dev/docs/svelte/v5-migration-guide)
- [Svelte 5 Runes](https://svelte.dev/docs/svelte/runes)
