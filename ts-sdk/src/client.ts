// Client for the chatnec connector service — use this when your agent wants to
// push a reply back asynchronously (e.g. after long-running work) instead of
// returning it synchronously from the webhook response.
import type { UniversalReply } from "./types.js";

export interface ChatConnectorClientOptions {
  baseUrl: string; // e.g. "https://your-connector.example.com"
  apiKey?: string; // matches REPLY_API_KEY on the connector, if set
}

export class ChatConnectorClient {
  constructor(private readonly options: ChatConnectorClientOptions) {}

  async reply(reply: UniversalReply): Promise<void> {
    const res = await fetch(`${this.options.baseUrl.replace(/\/$/, "")}/reply`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(this.options.apiKey ? { "X-API-Key": this.options.apiKey } : {}),
      },
      body: JSON.stringify(reply),
    });

    if (!res.ok) {
      throw new Error(`chatnec reply failed: ${res.status} ${await res.text()}`);
    }
  }
}
