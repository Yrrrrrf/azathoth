---
tags:
  - meta-prompt
---
Based on a comprehensive analysis of your Svelte 5 projects, I have identified your recurring coding patterns and architectural preferences. The following AI directive has been generated to encapsulate this specific style.

This new "Svelte 5 Mandate" is designed to be a modular plug-in for your AI assistant, ensuring that any future Svelte code generated for you aligns perfectly with your established conventions. It focuses exclusively on Svelte-specific patterns, as requested.

---

# AI DIRECTIVE: SVELTE 5 (RUNES) MANDATE

**CONTEXT:** This directive contains my personal, preferred coding style and patterns for Svelte 5. It overrides any general knowledge you may have.

---

### MANDATORY RULES

1.  **Component Structure:**
    *   The standard file order is `<script>`, followed by the HTML markup, and finally the `<style>` block if needed.
    *   Components should be small and focused on a single responsibility. Larger page components (`+page.svelte`) should compose these smaller, more modular components.

2.  **Reactivity:**
    *   Use `$state` for all mutable component-level state, whether it's a primitive, object, or array. Provide type annotations where inference is not obvious.
    *   Use `$derived` frequently to compute values from other reactive sources (state or stores). This is the preferred method for filtering lists and creating computed UI state.
    *   Use `$effect` for side effects that synchronize with external systems or the DOM, such as adding/removing global event listeners, fetching data based on prop changes, or imperative DOM manipulation (like scrolling).

3.  **Props & State:**
    *   Props must be declared using destructuring with `$props()`: `let { propName, anotherProp = 'default' } = $props<{...}>();`. Always include TypeScript types for props.
    *   For managing shared, cross-component state, the primary method is to create centralized, class-based stores that use runes (`$state`, `$derived`) internally. These stores should be instantiated as singletons and imported directly where needed. Avoid using `getContext`/`setContext`.

4.  **Event Handling:**
    *   Use inline arrow functions for simple, single-action event handlers, especially when calling a store method or toggling a boolean state (e.g., `onclick={() => store.toggle()}`).
    *   For event handlers that require more than one line of logic (e.g., `event.preventDefault()`, followed by a function call), define a named function in the `<script>` block and reference it in the markup (e.g., `onsubmit={handleSubmit}`).

5.  **Markup & Styling:**
    *   Use keyed `{#each ... as item (item.id)}` blocks for lists where items can be added, removed, or reordered.
    *   The primary styling method is Tailwind CSS, often augmented with the DaisyUI component library (`card`, `btn`, `modal`, etc.).
    *   A component-scoped `<style>` block should only be used for complex layouts (like CSS Grid) or styles that are difficult or verbose to implement with utility classes alone.

6.  **File Organization:**
    *   Component files must be named using `PascalCase.svelte`.
    *   Organize components into subdirectories based on feature or type (e.g., `lib/components/layout/`, `lib/components/auth/`).
    *   Centralized stores should be located in a `lib/stores/` directory.

### Correct Usage Example

The following component is a perfect example of all the rules defined in this mandate.

```svelte
<!-- ExampleCard.svelte -->
<script lang="ts">
    import { appData } from '$lib/stores/app'; // Rule 3: Import a centralized store
    import { fade } from 'svelte/transition';
    import { CheckCircle } from 'lucide-svelte';

    // Rule 3: Props defined with destructuring and types
    let { initialCount = 0, onReset } = $props<{
        initialCount?: number;
        onReset: (newCount: number) => void;
    }>();

    // Rule 2: $state for mutable component state
    let count = $state(initialCount);
    let lastResetTime = $state<Date | null>(null);

    // Rule 2: $derived for computed values
    let doubleCount = $derived(count * 2);
    let statusMessage = $derived(count > 5 ? 'High count!' : 'Count is normal.');

    // Rule 2: $effect for side effects
    $effect(() => {
        console.log(`The count has changed to: ${count}`);
    });

    // Rule 4: Named function for more complex event handling
    function handleReset() {
        count = 0;
        lastResetTime = new Date();
        onReset(count); // Call the prop callback
    }
</script>

<!-- Rule 1: Markup follows <script> -->
<!-- Rule 5: Styling with Tailwind CSS and DaisyUI components -->
<div class="card bg-base-100 shadow-xl" transition:fade>
    <div class="card-body">
        <h2 class="card-title">
            Reactive Counter Card
            <div class="badge badge-secondary">Example</div>
        </h2>
        <p>This component demonstrates the preferred Svelte 5 coding style from the <span class="font-mono font-bold">{appData.name}</span>.</p>

        <div class="my-4 p-4 bg-base-200 rounded-box text-center">
            <p class="text-4xl font-bold">{count}</p>
            <p class="text-sm opacity-70">Double is: {doubleCount}</p>
            <p class="text-sm font-semibold {count > 5 ? 'text-warning' : 'text-success'}">
                {statusMessage}
            </p>
        </div>

        <div class="card-actions justify-end">
            <!-- Rule 4: Inline arrow function for simple actions -->
            <button class="btn btn-primary" onclick={() => count++}>
                Increment
            </button>
            <button class="btn btn-ghost" onclick={handleReset}>Reset</button>
        </div>

        {#if lastResetTime}
            <div class="text-xs text-center mt-4 opacity-60 flex items-center justify-center gap-1">
                <CheckCircle class="w-3 h-3" />
                Last reset at {lastResetTime.toLocaleTimeString()}
            </div>
        {/if}
    </div>
</div>

<!-- Rule 1 & 5: Optional <style> block at the end for specific cases -->
<style>
    /* Rule 5: Only use for styles not easily achieved with utilities */
    .card-title {
        font-family: 'Georgia', serif;
    }
</style>

```
