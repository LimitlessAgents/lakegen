export type CatalogType = 'glue' | 'rest' | 'sql';
export type SqlDatabaseType = 'postgresql' | 'mysql' | 'sqlite';

export interface CatalogResponse {
  name: string;
  connected: boolean;
  lakehouse: string | null;
  catalog_type: CatalogType | null;
  warehouse: string | null;
}

export interface ErrorBody {
  code: string;
  message: string;
  details: Record<string, unknown> | null;
  cause: Record<string, unknown> | null;
  is_retryable: boolean;
  is_user_fixable: boolean;
}

export interface CreateSessionResponse {
  id: string;
}

export interface TurnRequest {
  text: string;
  catalog_name?: string | null;
  model?: string;
  provider?: string;
}

export type CatalogCreateRequest =
  | GlueCatalogCreate
  | RestCatalogCreate
  | SqlCatalogCreate;

interface CatalogCreateBase {
  lakehouse: 'iceberg';
  name: string;
  warehouse: string;
  access_key?: string;
  secret_key?: string;
  region?: string;
  endpoint?: string;
}

export interface GlueCatalogCreate extends CatalogCreateBase {
  catalog_type: 'glue';
  glue_catalog_id?: string;
  glue_access_key?: string;
  glue_secret_key?: string;
  glue_endpoint?: string;
  glue_region?: string;
}

export interface RestCatalogCreate extends CatalogCreateBase {
  catalog_type: 'rest';
  rest_catalog_url: string;
  credential?: string;
  oauth2_uri?: string;
  rest_auth_type?: string;
  token?: string;
  scope?: string;
  rest_signing_name?: string;
  rest_signing_region?: string;
  rest_signing_v_4?: boolean;
  no_identifier_fields?: boolean;
}

export interface SqlCatalogCreate extends CatalogCreateBase {
  catalog_type: 'sql';
  database_type: SqlDatabaseType;
  host: string;
  port?: number;
  username: string;
  password: string;
  database: string;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  streaming?: boolean;
  error?: string;
  createdAt: number;
}
