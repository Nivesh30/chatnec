// Mirrors chatnec.models (Python) exactly — this is the wire format posted to
// your agent's webhook endpoint by the connector service in HTTP mode.

export interface Attachment {
  type: string;
  url?: string;
  name?: string;
  content_type?: string;
}

export interface UniversalMessage {
  id: string;
  platform: string; // "slack" | "telegram" | "teams"
  chat_id: string;
  thread_id?: string;
  user_id: string;
  user_name?: string;
  text: string;
  attachments: Attachment[];
  timestamp: number;
  metadata: Record<string, unknown>;
  raw: Record<string, unknown>;
}

export interface UniversalReply {
  platform: string;
  chat_id: string;
  thread_id?: string;
  text: string;
  attachments?: Attachment[];
  metadata?: Record<string, unknown>;
}

export type AgentHandler = (
  message: UniversalMessage
) => Promise<string | Partial<UniversalReply> | null | undefined> | string | Partial<UniversalReply> | null | undefined;
