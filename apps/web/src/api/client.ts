import type {
  AgentTurnInfo,
  CatalogCreateRequest,
  CatalogResponse,
  CreateSessionResponse,
  ErrorBody,
  SessionResponse,
} from './types';

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly body: ErrorBody | null,
  ) {
    super(body?.message ?? `Request failed (${status})`);
    this.name = 'ApiError';
  }
}

async function parseError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as ErrorBody;
    if (body && typeof body.message === 'string') {
      return new ApiError(response.status, body);
    }
  } catch {
    /* ignore non-JSON */
  }
  return new ApiError(response.status, null);
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    throw await parseError(response);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function listCatalogs(): Promise<CatalogResponse[]> {
  return request('/v1/catalogs');
}

export function addCatalog(
  body: CatalogCreateRequest,
  signal?: AbortSignal,
): Promise<CatalogResponse> {
  return request('/v1/catalogs', {
    method: 'POST',
    body: JSON.stringify(body),
    signal,
  });
}

export function deleteCatalog(name: string): Promise<void> {
  return request(`/v1/catalogs/${encodeURIComponent(name)}`, {
    method: 'DELETE',
  });
}

export function createSession(): Promise<CreateSessionResponse> {
  return request('/v1/sessions', { method: 'POST' });
}

export function listSessions(offset = 0): Promise<SessionResponse[]> {
  return request(`/v1/sessions?offset=${offset}`);
}

export function listSessionTurns(
  sessionId: string,
  offset = 0,
  limit = 100,
  signal?: AbortSignal,
): Promise<AgentTurnInfo[]> {
  return request(
    `/v1/sessions/${encodeURIComponent(sessionId)}/turns?offset=${offset}&limit=${limit}`,
    { signal },
  );
}
