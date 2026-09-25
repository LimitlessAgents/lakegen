import type {
  GlueCatalogSpec,
  RestCatalogSpec,
  SqlCatalogSpec,
  ErrorCode,
} from './schema';

export type {
  AgentTurnInfo,
  CatalogResponse,
  CreateSessionResponse,
  ErrorCode,
  ErrorBody,
  SessionResponse,
  TurnRequest,
} from './schema';

export type CatalogCreateRequest =
  | GlueCatalogSpec
  | RestCatalogSpec
  | SqlCatalogSpec;

export type CatalogType = CatalogCreateRequest['catalog_type'];
export type SqlDatabaseType = SqlCatalogSpec['database_type'];

export type MessageStatus = 'streaming' | 'done' | 'stopped' | 'incomplete' | 'error';

interface MessageBase {
  id: string;
  text: string;
  createdAt: number;
}

export interface UserMessage extends MessageBase {
  role: 'user';
}

export interface AssistantMessage extends MessageBase {
  role: 'assistant';
  status: MessageStatus;
  errorMessage?: string;
  errorCode?: ErrorCode;
  retryText?: string;
  stopReason?: string;
}

export type Message = UserMessage | AssistantMessage;
