import type {
  GlueCatalogSpec,
  RestCatalogSpec,
  SqlCatalogSpec,
} from './schema';

export type {
  CatalogResponse,
  CreateSessionResponse,
  ErrorBody,
  TurnRequest,
} from './schema';

export type CatalogCreateRequest =
  | GlueCatalogSpec
  | RestCatalogSpec
  | SqlCatalogSpec;

export type CatalogType = CatalogCreateRequest['catalog_type'];
export type SqlDatabaseType = SqlCatalogSpec['database_type'];

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  streaming?: boolean;
  error?: string;
  createdAt: number;
}
