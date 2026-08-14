import type { ErrorBody, TurnRequest } from './types';
import { ApiError } from './client';

export type StreamEvent =
  | { type: 'text_delta'; data: { text: string } }
  | {
      type: 'turn_done';
      data: { final_message: string; stop_reason: string };
    }
  | { type: 'error'; data: ErrorBody };

export async function runTurn(
  sessionId: string,
  body: TurnRequest,
  onEvent: (event: StreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(
    `/v1/sessions/${encodeURIComponent(sessionId)}/turns`,
    {
      method: 'POST',
      headers: {
        Accept: 'text/event-stream',
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
      signal,
    },
  );
  if (!response.ok) {
    let parsed: ErrorBody | null = null;
    try {
      parsed = (await response.json()) as ErrorBody;
    } catch {
      /* ignore */
    }
    throw new ApiError(response.status, parsed);
  }
  if (!response.body) {
    throw new Error('Turn response had no body');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (value) {
      buffer += decoder.decode(value, { stream: true });
    }
    if (done) {
      buffer += decoder.decode();
    }

    buffer = dispatchSseBuffer(buffer, onEvent, done);
    if (done) break;
  }
}

function dispatchSseBuffer(
  buffer: string,
  onEvent: (event: StreamEvent) => void,
  flushRemainder: boolean,
): string {
  const normalized = buffer.replace(/\r\n/g, '\n');
  const parts = normalized.split('\n\n');
  const remainder = parts.pop() ?? '';

  for (const chunk of parts) {
    const event = parseSseChunk(chunk);
    if (event) onEvent(event);
  }

  if (flushRemainder && remainder.trim()) {
    const event = parseSseChunk(remainder);
    if (event) onEvent(event);
    return '';
  }

  return remainder;
}

function parseSseChunk(chunk: string): StreamEvent | null {
  let type = '';
  const dataLines: string[] = [];
  for (const line of chunk.split('\n')) {
    if (line.startsWith('event:')) {
      type = line.slice(6).trim();
      dataLines.length = 0;
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trim());
    }
  }
  if (!type || dataLines.length === 0) return null;
  try {
    const data = JSON.parse(dataLines.join('\n')) as StreamEvent['data'];
    if (type === 'text_delta' || type === 'turn_done' || type === 'error') {
      return { type, data } as StreamEvent;
    }
  } catch {
    return null;
  }
  return null;
}
