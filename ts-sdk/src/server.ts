// Turns any TS/JS agent function into the HTTP endpoint the Python connector
// service expects when run with AGENT_MODE=http. No framework dependency —
// works with LangChain.js, the Vercel AI SDK, a raw OpenAI call, anything.
import { createServer, IncomingMessage, ServerResponse, Server } from "node:http";
import type { AgentHandler, UniversalMessage } from "./types.js";

export interface AgentServerOptions {
  port?: number;
  path?: string; // defaults to "/agent"; must match AGENT_WEBHOOK_URL on the connector
}

export function createAgentServer(handler: AgentHandler, options: AgentServerOptions = {}): Server {
  const path = options.path ?? "/agent";

  const server = createServer(async (req: IncomingMessage, res: ServerResponse) => {
    if (req.method !== "POST" || req.url !== path) {
      res.writeHead(404).end();
      return;
    }

    try {
      const body = await readBody(req);
      const message = JSON.parse(body) as UniversalMessage;
      const result = await handler(message);

      res.writeHead(200, { "Content-Type": "application/json" });
      if (result == null) {
        res.end();
        return;
      }
      const payload = typeof result === "string" ? { text: result } : result;
      res.end(JSON.stringify(payload));
    } catch (err) {
      res.writeHead(500, { "Content-Type": "application/json" });
      res.end(JSON.stringify({ error: (err as Error).message }));
    }
  });

  if (options.port) {
    server.listen(options.port);
  }

  return server;
}

function readBody(req: IncomingMessage): Promise<string> {
  return new Promise((resolve, reject) => {
    let data = "";
    req.on("data", (chunk) => (data += chunk));
    req.on("end", () => resolve(data));
    req.on("error", reject);
  });
}
