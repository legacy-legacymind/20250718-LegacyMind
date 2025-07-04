
import DOMPurify from 'dompurify';
import { JSDOM } from 'jsdom';

const window = new JSDOM('').window;
const purify = DOMPurify(window);

/**
 * Sanitizes a string to remove potentially malicious HTML and script content.
 * @param input The string to sanitize.
 * @returns A sanitized string, or an empty string if the input is null or undefined.
 */
export function sanitizeInput(input: string | null | undefined): string {
  if (!input) {
    return '';
  }
  return purify.sanitize(input);
}

/**
 * Recursively sanitizes all string properties of an object.
 * @param obj The object to sanitize.
 * @returns A new object with all string properties sanitized.
 */
export function sanitizeObject<T extends object>(obj: T): T {
  const sanitizedObj = { ...obj };
  for (const key in sanitizedObj) {
    if (typeof sanitizedObj[key] === 'string') {
      (sanitizedObj as any)[key] = sanitizeInput(sanitizedObj[key] as any);
    } else if (typeof sanitizedObj[key] === 'object' && sanitizedObj[key] !== null) {
      (sanitizedObj as any)[key] = sanitizeObject(sanitizedObj[key] as any);
    }
  }
  return sanitizedObj;
}
