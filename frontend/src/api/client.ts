// Typed fetch wrapper with AbortController support, error normalization, an optional
// zod validation hook, and a compile-time switch to the offline mock backend.
import type { ZodType } from 'zod';
import { env } from '@/env';
import type { ErrorResponse } from '@/types';
import { mockFetch } from './mocks';

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: string | null;
  readonly body: ErrorResponse | null;
  constructor(status: number, body: ErrorResponse | null, fallback: string) {
    super(body?.message ?? fallback);
    this.name = 'ApiError';
    this.status = status;
    this.code = body?.code ?? `HTTP_${status}`;
    this.detail = body?.detail ?? null;
    this.body = body;
  }
}

export interface RequestOptions {
  method?: 'GET' | 'POST';
  /** JSON-serializable request body. */
  body?: unknown;
  /** Extra headers (e.g. Idempotency-Key). */
  headers?: Record<string, string>;
  signal?: AbortSignal;
  /** Query params; undefined/null entries are omitted. */
  query?: Record<string, string | number | boolean | undefined | null>;
  /** Optional zod schema; validates then returns the ORIGINAL payload typed as T. */
  schema?: ZodType;
}

function buildUrl(path: string, query?: RequestOptions['query']): string {
  const base = env.apiUrl; // '' for same-origin
  let url = `${base}${path}`;
  if (query) {
    const sp = new URLSearchParams();
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null && v !== '') sp.set(k, String(v));
    }
    const qs = sp.toString();
    if (qs) url += `?${qs}`;
  }
  return url;
}

async function parseError(res: Response): Promise<ApiError> {
  let body: ErrorResponse | null = null;
  try {
    body = (await res.json()) as ErrorResponse;
  } catch {
    body = null;
  }
  return new ApiError(res.status, body, `Request failed (${res.status})`);
}

/** Core typed request. Validates with `schema` when provided; returns payload typed as T. */
export async function apiFetch<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, headers = {}, signal, query, schema } = opts;

  if (env.useMocks) {
    const data = await mockFetch(path, { method, body, query });
    if (schema) schema.parse(data);
    return data as T;
  }

  const init: RequestInit = {
    method,
    headers: { Accept: 'application/json', ...headers },
    signal,
  };
  if (body !== undefined) {
    init.headers = { ...init.headers, 'Content-Type': 'application/json' };
    init.body = JSON.stringify(body);
  }

  let res: Response;
  try {
    res = await fetch(buildUrl(path, query), init);
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err;
    throw new ApiError(0, null, `Network error: ${(err as Error).message}`);
  }

  if (!res.ok) throw await parseError(res);

  const data = (await res.json()) as unknown;
  if (schema) schema.parse(data);
  return data as T;
}

/** Build an absolute URL for a binary/media resource (tiles, downloads) honoring apiUrl. */
export function mediaUrl(path: string): string {
  return `${env.apiUrl}${path}`;
}

/** A fresh AbortController; callers abort the previous when a request supersedes it. */
export function newAbort(): AbortController {
  return new AbortController();
}

export function isAbort(err: unknown): boolean {
  return err instanceof DOMException && err.name === 'AbortError';
}
