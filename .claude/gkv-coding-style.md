# GKV Coding Best Practices

## Function Signature Pattern

**ALWAYS use interface-based props pattern for functions with multiple parameters:**

```typescript
interface IFunctionProps {
  required: string;
  optional?: number;
}

export const myFunction = async (props: IFunctionProps): Promise<void> => {
  const { required, optional = defaultValue } = props;
  // Function body - lines MUST NOT break in signature
};
```

**Key Rules:**

- Use interfaces for function parameters instead of long parameter lists
- Single props object instead of multiple individual parameters
- Destructuring with defaults in function body
- Lines MUST NOT break in function signature
- Optional parameters marked with `?` in interface
- Default values assigned during destructuring

## Console Logging Standards

**Clean, professional logging without emotions:**

```typescript
// ❌ Don't use emotions/emojis
console.log("🎯 [Service] Starting process...");
console.error("❌ [Service] Process failed!");

// ✅ Clean, professional logs
console.log("[Service] Starting process");
console.error("[Service] Process failed:", error);
```

**Log Structure:**

- `[ServiceName]` prefix for context
- No emojis or emotional language
- Include relevant data objects for debugging
- Use appropriate log levels (log, error, warn)

## Informative Code Commenting

**Add clear, concise comments that explain WHAT each section does and expected INPUT/OUTPUT:**

```typescript
// ❌ Obvious or useless comments
const user = getUser(); // Get user
i++; // Increment i

// ❌ Emotional or unprofessional comments
// This is a crazy hack but it works! 🚀
// TODO: Fix this mess later

// ✅ Informative comments with purpose and data flow
export class ChatAgent {
  constructor(res: Response) {
    // Initialize chat tools (intent analyzer + chat responder) with response stream
    this.tools = ChatToolsFactory.createAllTools(res);
    // Configure LangChain ReAct agent with tools and prompt template
    this.setupAgent();
  }

  // Input: IChatAgentProps (messages, res, temperature, maxTokens, userId)
  // Output: void (streams response via res, saves to Firestore)
  async processChat(props: IChatAgentProps): Promise<void> {
    const { messages, temperature = 0.7, maxTokens = 13107, userId } = props;

    try {
      // Extract and validate latest user message from conversation
      const userMessage = messages[messages.length - 1];

      // Save user message to Firestore for persistence
      await MessageStorage.saveMessage(userId, userMessage);

      // Prepare conversation context (last 5 messages for memory efficiency)
      const last5Messages = messages.slice(-5);

      // Execute ReAct agent - it will decide which tools to use and stream response
      await this.agent.invoke(agentInput);
    } catch (error) {
      throw error;
    }
  }
}
```

**Comment Guidelines:**

- **Function signatures** - Always document expected input types and output behavior
- **Complex logic** - Explain what the code block accomplishes and why
- **Data transformations** - Describe what's being processed and the result
- **Business logic** - Explain the purpose and expected behavior
- **Professional tone** - No emotions, slang, or unprofessional language
- **Concise** - 1-2 lines maximum, focus on WHAT and WHY, not HOW

## Clean Code Standards

**ALWAYS follow these patterns for maximum readability and maintainability:**

### 1. One Statement Per Line

```typescript
// ❌ Complex nested calls
await SomeService.method(param1, param2, { prop: value, other: data });

// ✅ Clean, readable with variables
const data = { prop: value, other: data };
await SomeService.method(data);
```

### 2. Pre-create Data Objects

```typescript
// ❌ Long console.log lines
console.log("[ChatController] Controller called with:", {
  messagesCount: messages.length,
  userId,
  temperature,
});

// ✅ Clean with extracted data
const data = {
  messagesCount: messages.length,
  userId,
};
console.log("[ChatController] Chat controller called with:", data);
```

### 4. Simplified Error Handling

```typescript
// ❌ Complex error handling
} catch (error) {
  console.error("[Service] Failed:", error);
  const errorMessage = error instanceof Error ? error.message : "Unknown error occurred";
  res.status(500).json(getDataAsJSON(null, true, errorMessage));
}

// ✅ Clean with variable extraction
} catch (error) {
  console.error("[ChatController] Chat controller error:", error);
  const err = error instanceof Error ? error.message : "Unknown error";
  res.status(500).json(getDataAsJSON(null, true, err));
}
```

### 5. Variable Naming Conventions

- Use descriptive names: `intentData`, `chatData`, `err`
- Consistent patterns: `data` for objects, `err` for processed errors
- Avoid abbreviations except for well-known ones (`res`, `req`, `err`)

### 6. File Naming Conventions

**Use dot notation for file names instead of hyphens or underscores:**
First use the type of the file and the exact name.
| Type                                   | Naming                                    | Example                      |
| -------------------------------------- | ----------------------------------------- | ---------------------------- |
| React Component                        | **PascalCase.tsx**                        | `Social.tsx`                 |
| Page Component (Next.js / Router page) | **PascalCase.tsx**                        | `Dashboard.tsx`              |
| Hooks                                  | **camelCase.ts**                          | `useAuth.ts`                 |
| Utility files                          | **camelCase.ts**                          | `formatDate.ts`              |
| Context                                | **PascalCase.tsx**                        | `AuthContext.tsx`            |
| Types                                  | **PascalCase.ts**                         | `UserTypes.ts` or `types.ts` |
| Constants                              | **UPPER_SNAKE_CASE.ts** or `constants.ts` | `API_ROUTES.ts`              |




**Benefits:**

- **Clear hierarchy** - Dots indicate logical grouping and relationships
- **Better readability** - Easier to scan and understand file purposes
- **Consistent pattern** - Uniform approach across all file types
- **IDE friendly** - Many editors group files by dot notation automatically

**Key Principles:**

- **One concept per line** - Easy to read and debug
- **Extract complex data** - No inline complex objects
- **Consistent variable naming** - Predictable patterns
- **Clean service calls** - Always use data objects
- **Readable error handling** - Simple and consistent

## Prompt Organization

**ALWAYS separate prompts into dedicated files following this pattern:**

````typescript
// agents/prompt.agent.ts
export const CHAT_AGENT_SYSTEM_PROMPT = (): string => {
  return `You are a helpful AI assistant...`;
};

export const CHAT_AGENT_PROMPT_TEMPLATE = (): string => {
  return `${CHAT_AGENT_SYSTEM_PROMPT()}

Current conversation:
{messages}

User message: {input}
{agent_scratchpad}`;
};


### Interface Naming Conventions

**CRITICAL: All interfaces must follow these strict naming rules:**

```typescript
// ✅ Correct naming patterns
interface IMemoryChunk {
  // "I" prefix + descriptive name
  id: string;
  summary: string;
}

interface ICreateChunk {
  // "I" prefix + concise action (max 15 chars)
  userId: string;
  messages: StoredMessage[];
}

interface IQueryMemory {
  // "I" prefix + short descriptive name
  userId: string;
  queryText: string;
  topK?: number;
}

// ❌ Avoid these patterns
interface MemoryChunk {} // Missing "I" prefix
interface ICreateMemoryChunkProps {} // Too long (>15 chars)
interface IQuerySimilarMemoriesWithScoreThreshold {} // Way too long
````

**Key Rules:**

- **"I" prefix mandatory** - All interfaces must start with "I" to indicate interface type
- **Maximum 15 characters** - Keep interface names concise and readable
- **Descriptive but brief** - Use clear action words like Create, Query, Delete, Store
- **No redundant suffixes** - Avoid "Props", "Data", "Input" unless absolutely necessary

## Architecture Guidelines

### Key Principles

- **Single Responsibility** - Each file has one clear purpose
- **Interface-driven** - All complex parameters use interfaces
- **Prompt externalization** - Zero hardcoded strings
- **Clean separation** - Logic, types, validation, and prompts in separate files
- **Consistent patterns** - Same approach across all components
- **Validation isolation** - Zod schemas in dedicated validation.ts files
- **Type safety** - TypeScript interfaces in dedicated types.ts files

## AI Agent Patterns

### ReAct Agent Usage

- **Intelligent orchestration** - Agent decides which tools to use
- **Context awareness** - Uses conversation history effectively
- **Error handling** - Graceful failure recovery
- **Streaming support** - Real-time response delivery

### Tool Design

- **DynamicStructuredTool** - Use 2024 LangChain patterns
- **Zod validation** - Schema-based input validation
- **Clean interfaces** - Type-safe tool inputs and outputs
- **Backward compatibility** - Static methods for existing code

# Agent, AI, LLM

whenever dealign with AI related work, always refer to documentation provided by langchain. If required, do an internet search. We dont want to reinvent the wheel, there are a lot of out of box tools, packages available. Reuse them. Stay Upto date.

Remember: **These patterns ensure maintainable, readable, and professional code that scales effectively!**
