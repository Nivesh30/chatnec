// Any Node-based agent framework works the same way: do your framework-specific
// call inside the handler, return the text. Pairs with the Python connector
// running in HTTP mode (AGENT_MODE=http, AGENT_WEBHOOK_URL=http://localhost:9000/agent).
import { createAgentServer } from "@chatnec/sdk";

createAgentServer(
  async (message) => {
    // Swap this line for LangChain.js, the Vercel AI SDK, an OpenAI call, etc.
    return `You said: ${message.text}`;
  },
  { port: 9000 }
);

console.log("Agent listening on http://localhost:9000/agent");
