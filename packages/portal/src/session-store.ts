import { createHash } from "node:crypto";

import type { PortalKind } from "./types";

/**
 * Server-held portal session. Identity-provider tokens live only here; the browser
 * receives an opaque, random session identifier and never a bearer token.
 */
export interface PortalSessionRecord {
  v: number;
  kind: PortalKind;
  subject: string;
  userId: string;
  accessToken: string;
  accessExpiresAt: number;
  refreshToken: string;
  refreshExpiresAt: number;
  csrfToken: string;
  createdAt: number;
  lastSeenAt: number;
  absoluteExpiresAt: number;
}

export interface PortalSessionStore {
  get(id: string): Promise<PortalSessionRecord | null>;
  set(id: string, record: PortalSessionRecord): Promise<void>;
  delete(id: string): Promise<void>;
}

const DEFAULT_CAPACITY = 10_000;

/** Store keys are digests so a store dump cannot be replayed as browser cookies. */
function storageKey(id: string): string {
  return createHash("sha256").update(id).digest("base64url");
}

/**
 * Bounded in-process store. Portal containers run as a single replica; a restart
 * destroys every session, which fails closed to a fresh sign-in.
 */
export class MemoryPortalSessionStore implements PortalSessionStore {
  private readonly records = new Map<string, PortalSessionRecord>();

  constructor(
    private readonly capacity = DEFAULT_CAPACITY,
    private readonly clock: () => number = () => Math.floor(Date.now() / 1000),
  ) {}

  async get(id: string): Promise<PortalSessionRecord | null> {
    const key = storageKey(id);
    const record = this.records.get(key);
    if (!record) return null;
    if (record.absoluteExpiresAt <= this.clock() || record.refreshExpiresAt <= this.clock()) {
      this.records.delete(key);
      return null;
    }
    return { ...record };
  }

  async set(id: string, record: PortalSessionRecord): Promise<void> {
    const key = storageKey(id);
    this.records.delete(key);
    if (this.records.size >= this.capacity) this.evict();
    this.records.set(key, { ...record });
  }

  async delete(id: string): Promise<void> {
    this.records.delete(storageKey(id));
  }

  get size(): number {
    return this.records.size;
  }

  private evict(): void {
    const current = this.clock();
    for (const [key, record] of this.records) {
      if (record.absoluteExpiresAt <= current || record.refreshExpiresAt <= current) this.records.delete(key);
    }
    // Map iteration is insertion order, and set() re-inserts on write, so the first key is least recently written.
    while (this.records.size >= this.capacity) {
      const oldest = this.records.keys().next().value;
      if (oldest === undefined) break;
      this.records.delete(oldest);
    }
  }
}
