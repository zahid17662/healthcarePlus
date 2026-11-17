import { createHttpApi } from './http';
import { createMockApi } from './mockApi';
import type { HealthcareApi } from './types';

const baseUrl = (import.meta.env.VITE_API_URL as string | undefined)?.trim();

/** True when running against the in-browser mock instead of a real backend. */
export const isMockApi = !baseUrl;

export const api: HealthcareApi = baseUrl ? createHttpApi(baseUrl) : createMockApi();

export { tokenStore } from './tokenStore';
export type { HealthcareApi } from './types';
