
import { CacheError } from './errors.ts';

interface CacheEntry<T> {
  data: T;
  timestamp: number;
}

export class SimpleCache<T> {
  private cache = new Map<string, CacheEntry<T>>();
  private ttl: number;

  constructor(ttlSeconds: number = 60) {
    this.ttl = ttlSeconds * 1000;
  }

  get(key: string): T | undefined {
    const entry = this.cache.get(key);
    if (!entry) {
      return undefined;
    }

    if (Date.now() - entry.timestamp > this.ttl) {
      this.cache.delete(key);
      return undefined;
    }

    return entry.data;
  }

  set(key: string, value: T): void {
    try {
      const entry: CacheEntry<T> = {
        data: value,
        timestamp: Date.now(),
      };
      this.cache.set(key, entry);
    } catch (error) {
      throw new CacheError('Failed to set cache entry.');
    }
  }

  has(key: string): boolean {
    return this.get(key) !== undefined;
  }

  invalidate(key: string): void {
    this.cache.delete(key);
  }

  clear(): void {
    this.cache.clear();
  }
}
