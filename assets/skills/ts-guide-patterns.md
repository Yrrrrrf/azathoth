# Advanced TypeScript Patterns Guide
## A Playbook for Writing Powerful, Type-Safe, Boilerplate-Free Code

---

## Table of Contents

1. [Introduction](#introduction)
2. [Pattern 1: Generic Config Store Factory](#pattern-1-generic-config-store-factory)
3. [Pattern 2: Type-Level Programming with Template Literals](#pattern-2-type-level-programming-with-template-literals)
4. [Pattern 3: Proxy-Based Auto-Validation](#pattern-3-proxy-based-auto-validation)
5. [Pattern 4: Discriminated Union Actions](#pattern-4-discriminated-union-actions)
6. [Pattern 5: Higher-Order Functions for Component Generation](#pattern-5-higher-order-functions-for-component-generation)
7. [Pattern 6: Const Assertions + Mapped Types](#pattern-6-const-assertions--mapped-types)
8. [Pattern 7: Schema as Single Source of Truth (Zod)](#pattern-7-schema-as-single-source-of-truth-zod)
9. [Pattern 8: Builder Pattern with Fluent Generics](#pattern-8-builder-pattern-with-fluent-generics)
10. [Pattern Comparison Matrix](#pattern-comparison-matrix)
11. [Best Practices](#best-practices)

---

## Introduction

This guide presents advanced TypeScript patterns inspired by Rust's declarative and procedural macros. These patterns eliminate boilerplate, enforce type safety at compile-time, and make code more maintainable.

**Core Principles:**
- **DRY (Don't Repeat Yourself):** Write once, use everywhere
- **Type Safety:** Let the compiler catch bugs
- **Declarative:** Define what, not how
- **Zero-Cost Abstractions:** No runtime overhead

**When to use these patterns:**
- ✅ Multiple similar implementations exist
- ✅ Type safety is critical
- ✅ You're repeating validation/transformation logic
- ✅ You want compile-time guarantees

---

## Pattern 1: Generic Config Store Factory

### Problem
Managing multiple configuration stores (themes, languages, currencies) requires duplicating validation, persistence, and getter logic across ~100 lines per store.

### Solution
A generic factory that creates type-safe stores with built-in functionality.

### Implementation

```typescript
// config-store.svelte.ts

interface ConfigItem {
    [key: string]: any;
}

interface ConfigStoreOptions<T extends ConfigItem> {
    /** Array of available items */
    items: readonly T[];
    /** LocalStorage key */
    storageKey: string;
    /** Display name for logging (e.g., "Theme", "Language") */
    displayName: string;
    /** Key to use as identifier (e.g., "code", "name") */
    idKey: keyof T;
    /** Icon for logs */
    icon?: string;
}

/**
 * Creates a reactive configuration store with persistence
 */
export function createConfigStore<T extends ConfigItem>(
    options: ConfigStoreOptions<T>
) {
    const { items, storageKey, displayName, idKey, icon = "⚙️" } = options;

    class ConfigStore {
        current: T[typeof idKey] = $state("" as T[typeof idKey]);
        available: T[] = $state([...items] as T[]);

        constructor() {
            if (typeof window !== "undefined") {
                const saved = localStorage.getItem(storageKey);
                if (saved && this.get(saved)) {
                    this.current = saved as T[typeof idKey];
                }
            }
            console.log(`${icon} ${displayName} configured:`, {
                current: this.current,
            });
        }

        /**
         * Set current item with validation
         */
        set(id: T[typeof idKey]): void {
            const item = this.get(id);
            if (!item) {
                console.warn(`${displayName} "${id}" not found`);
                return;
            }
            this.current = id;
            localStorage.setItem(storageKey, String(id));
        }

        /**
         * Get item by id
         */
        get(id: T[typeof idKey]): T | undefined {
            return this.available.find(item => item[idKey] === id);
        }

        /**
         * Get property from current or specified item
         */
        getProp<K extends keyof T>(prop: K, id?: T[typeof idKey]): T[K] | undefined {
            const targetId = id ?? this.current;
            return this.get(targetId)?.[prop];
        }
    }

    return new ConfigStore();
}
```

### Usage

```typescript
// theme-config.svelte.ts
import { createConfigStore } from "./config-store.svelte";

export interface Theme {
    name: string;
    icon: string;
}

const THEMES = [
    { name: "light", icon: "🌞" },
    { name: "dark", icon: "🌙" },
    { name: "cyberpunk", icon: "🤖" },
] as const;

export const themeStore = createConfigStore({
    items: THEMES,
    storageKey: "theme",
    displayName: "Theme",
    idKey: "name",
    icon: "🎨",
});

// Usage in components:
themeStore.set("dark");
themeStore.get("dark");
themeStore.getProp("icon"); // gets icon of current theme
themeStore.getProp("icon", "dark"); // gets icon of specific theme
```

```typescript
// language-config.svelte.ts
export interface Language {
    code: string;
    name: string;
    flag?: string;
}

export const languageStore = createConfigStore({
    items: LANGUAGES,
    storageKey: "language",
    displayName: "Language",
    idKey: "code",
    icon: "🌍",
});
```

```typescript
// currency-config.svelte.ts
export interface Currency {
    code: string;
    name: string;
    symbol: string;
    decimals: number;
}

export const currencyStore = createConfigStore({
    items: CURRENCIES,
    storageKey: "currency",
    displayName: "Currency",
    idKey: "code",
    icon: "💰",
});
```

### Benefits

| Metric | Before | After | Savings |
|--------|--------|-------|---------|
| Lines per store | ~100 | ~10 | 90% |
| Total lines (3 stores) | ~300 | ~80 | 73% |
| Consistency | ❌ | ✅ | Perfect |
| Type safety | ⚠️ | ✅ | Full inference |

**Key advantages:**
- ✅ Universal `getProp()` replaces all custom getters
- ✅ Consistent validation (warn + no-op, never throw)
- ✅ Automatic persistence
- ✅ Full TypeScript inference
- ✅ Easy to extend with new methods

### When to Use

✅ **Use when:**
- Multiple similar stores (settings, configs, catalogs)
- Same validation/persistence logic
- Type-safe property access needed

❌ **Don't use when:**
- Stores have very different behavior
- Complex business logic per store
- Only 1-2 stores total

---

## Pattern 2: Type-Level Programming with Template Literals

### Problem
Manually maintaining action types for entities leads to typos, missing combinations, and inconsistent naming.

### Solution
Use TypeScript's template literal types to auto-generate all valid combinations at compile-time.

### Implementation

```typescript
// Auto-generate action types from entity names
type Entity = "user" | "post" | "comment";
type Action = "create" | "update" | "delete" | "read";

// Generates all combinations: "user/create" | "user/update" | ...
type EntityAction = `${Entity}/${Action}`;

// Use with handlers - TypeScript enforces ALL combinations
const handlers: Record<EntityAction, (data: any) => void> = {
    "user/create": (data) => { /* ... */ },
    "user/update": (data) => { /* ... */ },
    "user/delete": (data) => { /* ... */ },
    "user/read": (data) => { /* ... */ },
    "post/create": (data) => { /* ... */ },
    // TypeScript will error if ANY combination is missing!
    // ... must implement all 12 combinations (3 entities × 4 actions)
};

// Type-safe dispatch
function dispatch(action: EntityAction, data: any) {
    handlers[action](data);
}

dispatch("user/create", { name: "Alice" }); // ✅
dispatch("user/invalid", {}); // ❌ Compile error!
```

### Advanced: Nested Routes

```typescript
type Method = "GET" | "POST" | "PUT" | "DELETE";
type Version = "v1" | "v2";
type Resource = "users" | "posts";

type APIEndpoint = `/${Version}/${Resource}`;
type APIRoute = `${Method} ${APIEndpoint}`;

// Generates: "GET /v1/users" | "POST /v1/users" | "GET /v2/posts" | ...
const routes: Record<APIRoute, () => void> = {
    "GET /v1/users": () => {},
    "POST /v1/users": () => {},
    // ... must implement all combinations
};
```

### Benefits
- ✅ **Exhaustiveness:** Compiler enforces all combinations
- ✅ **No typos:** Auto-completion works perfectly
- ✅ **Refactor-safe:** Rename entity, all actions update
- ✅ **Self-documenting:** Types show all valid options

### When to Use

✅ **Use when:**
- Action/entity combinations
- Route definitions
- Event naming conventions
- State machine transitions

❌ **Don't use when:**
- Too many combinations (10+ × 10+ = explosion)
- Dynamic/runtime-only values

---

## Pattern 3: Proxy-Based Auto-Validation

### Problem
Manual validation before every property assignment is verbose and error-prone.

### Solution
Use JavaScript Proxies to intercept property assignments and validate automatically.

### Implementation

```typescript
/**
 * Creates a validated object using Proxy
 * Like Rust's trait bounds, but at runtime
 */
function createValidated<T extends object>(
    obj: T,
    schema: Record<keyof T, (val: any) => boolean>
): T {
    return new Proxy(obj, {
        set(target, prop, value) {
            // Validate if schema exists for this property
            if (prop in schema && !schema[prop as keyof T](value)) {
                throw new Error(
                    `Validation failed for ${String(prop)}: ${value}`
                );
            }
            target[prop as keyof T] = value;
            return true;
        }
    });
}

// Usage
interface User {
    name: string;
    age: number;
    email: string;
}

const user = createValidated<User>(
    { name: "", age: 0, email: "" },
    {
        name: (v) => typeof v === "string" && v.length > 2,
        age: (v) => typeof v === "number" && v >= 18,
        email: (v) => typeof v === "string" && v.includes("@"),
    }
);

// Automatic validation on EVERY assignment!
user.age = 15;  // ❌ Throws: "Validation failed for age: 15"
user.age = 20;  // ✅ Works
user.name = "A"; // ❌ Throws: "Validation failed for name: A"
user.email = "invalid"; // ❌ Throws
user.email = "test@example.com"; // ✅ Works
```

### Advanced: With TypeScript Narrowing

```typescript
/**
 * Validated object with type narrowing
 */
function createStrictValidated<T extends object>(
    schema: { [K in keyof T]: (val: any) => val is T[K] }
): T {
    const obj = {} as T;
    return new Proxy(obj, {
        set(target, prop, value) {
            const validator = schema[prop as keyof T];
            if (!validator(value)) {
                throw new Error(`Invalid ${String(prop)}`);
            }
            target[prop as keyof T] = value;
            return true;
        }
    });
}

// With type guards
const strictUser = createStrictValidated<User>({
    name: (v): v is string => typeof v === "string" && v.length > 2,
    age: (v): v is number => typeof v === "number" && v >= 18,
    email: (v): v is string => typeof v === "string" && v.includes("@"),
});
```

### Benefits
- ✅ **Zero boilerplate:** Write validation once
- ✅ **Impossible to forget:** Every assignment validated
- ✅ **Centralized rules:** All validation in one place
- ✅ **Runtime safety:** Catches invalid data at the source

### When to Use

✅ **Use when:**
- Form data validation
- API response validation
- Configuration objects
- User input handling

❌ **Don't use when:**
- Performance-critical hot paths (Proxy has overhead)
- Need compile-time validation only (use Zod instead)

---

## Pattern 4: Discriminated Union Actions

### Problem
Loose action types in state management lead to runtime errors and poor type inference.

### Solution
Use discriminated unions (like Rust enums) for type-safe state transitions.

### Implementation

```typescript
/**
 * Discriminated union actions - like Rust enums
 * Each variant can have different payload types
 */
type Action =
    | { type: "increment" }
    | { type: "decrement" }
    | { type: "set"; value: number }
    | { type: "multiply"; factor: number }
    | { type: "reset"; default?: number };

function reducer(state: number, action: Action): number {
    switch (action.type) {
        case "increment":
            return state + 1;
        case "decrement":
            return state - 1;
        case "set":
            // TypeScript KNOWS 'value' exists here!
            return action.value;
        case "multiply":
            // And 'factor' exists here!
            return state * action.factor;
        case "reset":
            // Optional properties work too!
            return action.default ?? 0;
    }
    // Exhaustiveness checking - compiler ensures all cases handled
}

// Type-safe dispatch
const newState = reducer(10, { type: "multiply", factor: 2 }); // ✅ 20
const invalid = reducer(10, { type: "multiply" }); // ❌ Missing 'factor'
const typo = reducer(10, { type: "mult", factor: 2 }); // ❌ Invalid type
```

### Advanced: Async Actions

```typescript
type AsyncAction =
    | { type: "fetch/start"; url: string }
    | { type: "fetch/success"; data: any }
    | { type: "fetch/error"; error: Error }
    | { type: "fetch/cancel"; reason?: string };

type State = {
    status: "idle" | "loading" | "success" | "error";
    data: any;
    error: Error | null;
};

function asyncReducer(state: State, action: AsyncAction): State {
    switch (action.type) {
        case "fetch/start":
            return { ...state, status: "loading" };
        case "fetch/success":
            return { status: "success", data: action.data, error: null };
        case "fetch/error":
            return { status: "error", data: null, error: action.error };
        case "fetch/cancel":
            return { ...state, status: "idle" };
    }
}
```

### Benefits
- ✅ **Exhaustive matching:** Compiler ensures all cases handled
- ✅ **Type narrowing:** Correct payload types in each branch
- ✅ **Refactor-safe:** Add/remove variants, compiler guides you
- ✅ **Self-documenting:** All possible actions in one type

### When to Use

✅ **Use when:**
- State machines
- Redux/Zustand actions
- Event handlers with multiple types
- Command patterns

❌ **Don't use when:**
- Actions share same payload structure
- Simple boolean flags suffice

---

## Pattern 5: Higher-Order Functions for Component Generation

### Problem
Manually creating CRUD components for each entity requires duplicating list, form, and detail views.

### Solution
Use higher-order functions to generate components programmatically.

### Implementation

```typescript
/**
 * Generate CRUD components for any entity
 * Like Rust's derive macros for traits
 */
function createCRUD<T extends { id: string }>(
    entityName: string,
    fields: (keyof T)[]
) {
    return {
        List: (props: { items: T[] }) => {
            return {
                render: () => `
                    <ul>
                        ${props.items.map(item => 
                            `<li>${item.id}: ${fields.map(f => item[f]).join(', ')}</li>`
                        ).join('')}
                    </ul>
                `
            };
        },

        Form: (props: { onSubmit: (data: T) => void }) => {
            return {
                render: () => `
                    <form>
                        ${fields.map(field => 
                            `<input name="${String(field)}" placeholder="${String(field)}" />`
                        ).join('')}
                        <button type="submit">Create ${entityName}</button>
                    </form>
                `
            };
        },

        Detail: (props: { item: T }) => {
            return {
                render: () => `
                    <div>
                        <h2>${entityName} Details</h2>
                        ${fields.map(field => 
                            `<p><strong>${String(field)}:</strong> ${props.item[field]}</p>`
                        ).join('')}
                    </div>
                `
            };
        },
    };
}

// Usage - one line creates 3 components!
interface User {
    id: string;
    name: string;
    email: string;
    role: string;
}

const UserCRUD = createCRUD<User>("User", ["name", "email", "role"]);

// Now you have:
// - UserCRUD.List
// - UserCRUD.Form
// - UserCRUD.Detail
```

### Svelte-Specific Version

```typescript
// For Svelte components
function createSvelteCRUD<T extends { id: string }>(
    entityName: string,
    fields: (keyof T)[]
) {
    return {
        List: class {
            items = $state<T[]>([]);
            
            constructor(items: T[]) {
                this.items = items;
            }
        },

        Form: class {
            data = $state<Partial<T>>({});
            onSubmit: (data: T) => void;

            constructor(onSubmit: (data: T) => void) {
                this.onSubmit = onSubmit;
            }

            handleSubmit() {
                this.onSubmit(this.data as T);
            }
        },
    };
}
```

### Benefits
- ✅ **DRY:** Define once, generate many
- ✅ **Consistent:** All CRUD follows same pattern
- ✅ **Type-safe:** Full inference on generated components
- ✅ **Easy updates:** Change factory, all components update

### When to Use

✅ **Use when:**
- Admin panels
- CRUD applications
- Repeated UI patterns
- Form generators

❌ **Don't use when:**
- Each entity needs unique UI
- Complex custom layouts
- Over-engineering simple cases

---

## Pattern 6: Const Assertions + Mapped Types

### Problem
Defining routes, configs, or constants requires maintaining separate types and runtime values.

### Solution
Use `as const` to derive types from data, making data the single source of truth.

### Implementation

```typescript
/**
 * Define once, derive everything
 * Like Rust's const generics
 */
const ROUTES = {
    home: "/",
    profile: "/profile/:id",
    settings: "/settings",
    post: "/posts/:postId",
    comment: "/posts/:postId/comments/:commentId",
} as const;

// Auto-generate route names
type RouteName = keyof typeof ROUTES;
// Result: "home" | "profile" | "settings" | "post" | "comment"

// Extract parameter names from route paths
type ExtractParams<T extends string> = 
    T extends `${infer Start}:${infer Param}/${infer Rest}`
        ? { [K in Param | keyof ExtractParams<`/${Rest}`>]: string }
        : T extends `${infer Start}:${infer Param}`
            ? { [K in Param]: string }
            : {};

// Get params for specific route
type RouteParams<T extends RouteName> = ExtractParams<typeof ROUTES[T]>;

// Usage - fully typed!
function navigate<T extends RouteName>(
    route: T,
    ...args: {} extends RouteParams<T> ? [] : [RouteParams<T>]
) {
    // Implementation
}

navigate("home"); // ✅ No params needed
navigate("profile", { id: "123" }); // ✅ Requires id
navigate("profile"); // ❌ Error: missing id parameter
navigate("post", { postId: "456" }); // ✅ Requires postId
navigate("comment", { postId: "1", commentId: "2" }); // ✅ Both params
```

### Advanced: With HTTP Methods

```typescript
const API_ROUTES = {
    getUsers: { method: "GET", path: "/users" },
    createUser: { method: "POST", path: "/users" },
    getUser: { method: "GET", path: "/users/:id" },
    updateUser: { method: "PUT", path: "/users/:id" },
    deleteUser: { method: "DELETE", path: "/users/:id" },
} as const;

type APIRouteName = keyof typeof API_ROUTES;
type APIMethod = typeof API_ROUTES[APIRouteName]["method"];

// Type-safe API client
function apiCall<T extends APIRouteName>(
    route: T,
    params: ExtractParams<typeof API_ROUTES[T]["path"]>
) {
    const { method, path } = API_ROUTES[route];
    // Build URL with params...
}

apiCall("getUser", { id: "123" }); // ✅
apiCall("getUsers", {}); // ✅
apiCall("getUser", {}); // ❌ Missing id
```

### Benefits
- ✅ **Single source of truth:** Data defines types
- ✅ **No drift:** Types automatically update with data
- ✅ **Type extraction:** Complex types derived automatically
- ✅ **Refactor-safe:** Change data, types follow

### When to Use

✅ **Use when:**
- Route definitions
- Configuration objects
- Enum-like constants
- API endpoint definitions

❌ **Don't use when:**
- Values change at runtime
- Need actual enums with methods
- Complex type transformations hurt readability

---

## Pattern 7: Schema as Single Source of Truth (Zod)

### Problem
Maintaining separate TypeScript types and runtime validators leads to drift and bugs.

### Solution
Use Zod schemas as the single source of truth for both types and validation.

### Implementation

```typescript
import { z } from "zod";

/**
 * Schema IS the type AND the validator
 * Like Rust's serde + type system combined
 */

// Define schema once
const UserSchema = z.object({
    id: z.string().uuid(),
    name: z.string().min(2).max(100),
    email: z.string().email(),
    age: z.number().int().min(18).max(120),
    role: z.enum(["admin", "user", "guest"]),
    createdAt: z.date(),
    metadata: z.record(z.string(), z.any()).optional(),
});

// Derive TypeScript type from schema
type User = z.infer<typeof UserSchema>;
// No need to write:
// interface User { id: string; name: string; ... }

// Use for validation
function createUser(data: unknown): User {
    // Validates AND transforms to User type
    return UserSchema.parse(data);
}

// Safe parsing (doesn't throw)
function tryCreateUser(data: unknown): User | null {
    const result = UserSchema.safeParse(data);
    if (result.success) {
        return result.data;
    } else {
        console.error(result.error);
        return null;
    }
}

// Partial updates
const UpdateUserSchema = UserSchema.partial();
type UpdateUser = z.infer<typeof UpdateUserSchema>;

// Custom validation
const PasswordSchema = z.string()
    .min(8, "Too short")
    .regex(/[A-Z]/, "Must contain uppercase")
    .regex(/[0-9]/, "Must contain number");
```

### Advanced: Nested Schemas

```typescript
const AddressSchema = z.object({
    street: z.string(),
    city: z.string(),
    zipCode: z.string().regex(/^\d{5}$/),
    country: z.string().length(2), // ISO country code
});

const CompanySchema = z.object({
    name: z.string(),
    employees: z.array(UserSchema),
    headquarters: AddressSchema,
    founded: z.date(),
});

type Company = z.infer<typeof CompanySchema>;
// Automatically includes nested Address and User[] types!
```

### With Discriminated Unions

```typescript
const EventSchema = z.discriminatedUnion("type", [
    z.object({
        type: z.literal("click"),
        x: z.number(),
        y: z.number(),
    }),
    z.object({
        type: z.literal("keypress"),
        key: z.string(),
        ctrlKey: z.boolean(),
    }),
    z.object({
        type: z.literal("scroll"),
        deltaY: z.number(),
    }),
]);

type Event = z.infer<typeof EventSchema>;
// Result: discriminated union with type narrowing!
```

### Benefits
- ✅ **No drift:** Type and validation always in sync
- ✅ **Runtime safety:** Validate external data (APIs, forms)
- ✅ **Type inference:** Write schema, get types free
- ✅ **Composable:** Build complex schemas from simple ones
- ✅ **Error messages:** Detailed validation errors out of the box

### When to Use

✅ **Use when:**
- API request/response validation
- Form validation
- Configuration parsing
- Environment variables
- External data sources

❌ **Don't use when:**
- Internal types that never face external data
- Performance-critical paths (validation has overhead)
- Simple types where TypeScript alone suffices

---

## Pattern 8: Builder Pattern with Fluent Generics

### Problem
Creating complex objects with optional configurations is error-prone and hard to validate.

### Solution
Use a builder pattern with TypeScript generics to enforce required steps at compile-time.

### Implementation

```typescript
/**
 * Builder pattern with compile-time validation
 * Like Rust's typestate pattern
 */

// Track which builder methods have been called
type BuilderState = {
    hasWhere?: boolean;
    hasSelect?: boolean;
    hasFrom?: boolean;
};

class QueryBuilder<State extends BuilderState = {}> {
    private query: Partial<{
        from: string;
        where: string;
        select: string[];
        orderBy: string;
    }> = {};

    // Each method returns a new type with updated state
    from<T extends string>(table: T): QueryBuilder<State & { hasFrom: true }> {
        this.query.from = table;
        return this as any;
    }

    where(condition: string): QueryBuilder<State & { hasWhere: true }> {
        this.query.where = condition;
        return this as any;
    }

    select(...fields: string[]): QueryBuilder<State & { hasSelect: true }> {
        this.query.select = fields;
        return this as any;
    }

    orderBy(field: string): QueryBuilder<State> {
        this.query.orderBy = field;
        return this;
    }

    // Build requires all mandatory steps to be completed
    build(
        this: QueryBuilder<{
            hasFrom: true;
            hasWhere: true;
            hasSelect: true;
        }>
    ): Query {
        return {
            from: this.query.from!,
            where: this.query.where!,
            select: this.query.select!,
            orderBy: this.query.orderBy,
        };
    }
}

interface Query {
    from: string;
    where: string;
    select: string[];
    orderBy?: string;
}

// Usage - compiler enforces order!
const query1 = new QueryBuilder()
    .from("users")
    .where("id > 10")
    .select("name", "email")
    .build(); // ✅ All required methods called

const query2 = new QueryBuilder()
    .from("users")
    .select("name")
    .build(); // ❌ Error: missing where()

const query3 = new QueryBuilder()
    .where("id > 10")
    .build(); // ❌ Error: missing from() and select()
```

### Advanced: With Conditional Methods

```typescript
class HTTPRequestBuilder<State extends BuilderState = {}> {
    private config: any = {};

    method<M extends "GET" | "POST" | "PUT" | "DELETE">(
        method: M
    ): HTTPRequestBuilder<State & { hasMethod: true }> {
        this.config.method = method;
        return this as any;
    }

    url(url: string): HTTPRequestBuilder<State & { hasUrl: true }> {
        this.config.url = url;
        return this as any;
    }

    // Body only available after POST/PUT method is set
    body(
        this: HTTPRequestBuilder<State & { hasMethod: true }>,
        data: any
    ): HTTPRequestBuilder<State> {
        this.config.body = data;
        return this;
    }

    headers(headers: Record<string, string>): HTTPRequestBuilder<State> {
        this.config.headers = headers;
        return this;
    }

    build(
        this: HTTPRequestBuilder<{ hasMethod: true; hasUrl: true }>
    ): RequestConfig {
        return this.config;
    }
}

// Usage
const request = new HTTPRequestBuilder()
    .method("POST")
    .url("/api/users")
    .body({ name: "Alice" }) // ✅ body() available after method()
    .headers({ "Content-Type": "application/json" })
    .build();

const invalid = new HTTPRequestBuilder()
    .url("/api/users")
    .body({ name: "Alice" }) // ❌ body() not available before method()
    .build();
```

### Benefits
- ✅ **Compile-time validation:** Can't build incomplete objects
- ✅ **Method chaining:** Fluent, readable API
- ✅ **Conditional methods:** Some methods only available in certain states
- ✅ **Type-safe:** Full inference through the chain

### When to Use

✅ **Use when:**
- Complex object construction
- Multi-step processes with required steps
- DSLs (Domain-Specific Languages)
- Configuration builders

❌ **Don't use when:**
- Simple object creation (just use object literals)
- No required fields/steps
- Over-engineering simple cases

---

## Pattern Comparison Matrix

| Pattern | Lines Saved | Type Safety | Runtime Cost | Learning Curve | Best For |
|---------|-------------|-------------|--------------|----------------|----------|
| **Config Store Factory** | 90% | ✅✅✅ | Low | Medium | Multiple similar stores |
| **Template Literals** | 70% | ✅✅✅ | None | Low | Action/route naming |
| **Proxy Validation** | 80% | ✅✅ | Medium | Medium | Runtime validation |
| **Discriminated Unions** | 40% | ✅✅✅ | None | Low | State machines |
| **HOF Components** | 85% | ✅✅ | Low | High | CRUD generation |
| **Const Assertions** | 60% | ✅✅✅ | None | Medium | Config/routes |
| **Zod Schemas** | 50% | ✅✅✅ | Medium | Low | External data |
| **Builder Pattern** | 30% | ✅✅✅ | Low | High | Complex construction |

**Legend:**
- Lines Saved: % of boilerplate eliminated
- Type Safety: ✅ (basic) to ✅✅✅ (maximum)
- Runtime Cost: None < Low < Medium < High
- Learning Curve: How hard to understand/implement

---

## Best Practices

### 1. Choose the Right Pattern

**Decision Tree:**
```
Need to reduce boilerplate?
├─ Yes → Multiple similar implementations?
│  ├─ Yes → Config Store Factory or HOF
│  └─ No → Consider Discriminated Unions or Template Literals
└─ No → Need compile-time safety?
   ├─ Yes → Builder Pattern or Const Assertions
   └─ No → Need runtime validation?
      ├─ Yes → Zod or Proxy Validation
      └─ No → Keep it simple!
```

### 2. Don't Over-Engineer

**Red Flags:**
- ❌ Pattern is more complex than the problem
- ❌ Team doesn't understand the pattern
- ❌ Only 2-3 instances (not worth abstracting)
- ❌ Requirements change frequently

**Green Lights:**
- ✅ 5+ similar implementations
- ✅ Pattern is well-documented
- ✅ Team is comfortable with TypeScript generics
- ✅ Requirements are stable

### 3. Progressive Enhancement

Start simple, add patterns when needed:

```typescript
// Stage 1: Manual implementation
class ThemeStore { /* 100 lines */ }
class CurrencyStore { /* 100 lines */ }

// Stage 2: Notice duplication
// "These look really similar..."

// Stage 3: Extract pattern
const themeStore = createConfigStore({...});
const currencyStore = createConfigStore({...});

// Stage 4: Extend as needed
// Add new methods to factory when ALL stores need them
```

### 4. Document Your Patterns

Every pattern should have:
- ✅ **Why:** Problem it solves
- ✅ **When:** Use cases and anti-patterns
- ✅ **How:** Implementation example
- ✅ **Gotchas:** Common mistakes

### 5. Type Safety First

**Priority Order:**
1. Compile-time errors (best)
2. Runtime errors with good messages
3. Silent failures (worst)

**Example:**
```typescript
// ❌ Bad: Silent failure
function setTheme(name: string) {
    if (themes.includes(name)) {
        current = name;
    }
    // No feedback if theme not found!
}

// ⚠️ Better: Runtime error
function setTheme(name: string) {
    if (!themes.includes(name)) {
        throw new Error(`Theme ${name} not found`);
    }
    current = name;
}

// ✅ Best: Compile-time error
function setTheme(name: ThemeName) {
    // TypeScript ensures name is valid!
    current = name;
}
```

### 6. Performance Considerations

**Pattern Overhead:**
- **Zero cost:** Template Literals, Const Assertions, Discriminated Unions
- **Low cost:** Config Store Factory, Builder Pattern
- **Medium cost:** Proxy Validation, Zod Schemas
- **High cost:** HOF with complex rendering

**When performance matters:**
- Measure first, optimize second
- Consider memoization for HOF
- Use lazy initialization for factories
- Cache Zod validation results

### 7. Team Adoption

**Introduce Patterns Gradually:**
1. Start with simple patterns (Discriminated Unions, Const Assertions)
2. Document with examples
3. Pair program to teach
4. Gather feedback
5. Iterate and improve

**Create Pattern Library:**
```
/patterns
  /config-store
    - PATTERN.md
    - example.ts
    - test.spec.ts
  /builder
    - PATTERN.md
    - example.ts
```

---

## Conclusion

These patterns, inspired by Rust's macro system and type safety, bring compile-time guarantees and zero-cost abstractions to TypeScript. They eliminate boilerplate while maintaining (or improving) type safety.

**Key Takeaways:**
- **Generic Factory:** When you have 3+ similar implementations
- **Template Literals:** For exhaustive string combinations
- **Discriminated Unions:** For type-safe state machines
- **Const Assertions:** For deriving types from data
- **Zod Schemas:** For runtime validation with type inference
- **Builder Pattern:** For enforcing construction order

**Remember:**
- Start simple, add patterns when pain points emerge
- Type safety > brevity
- Document your patterns
- Measure performance when it matters
- Get team buy-in before introducing complex patterns

Happy pattern matching! 🦀✨