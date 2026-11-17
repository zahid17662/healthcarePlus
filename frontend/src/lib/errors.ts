export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

/** HTTP 409 — the slot was claimed by someone else. */
export const SLOT_CONFLICT = 409;

export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return 'Something went wrong. Please try again.';
}

export function isSlotConflict(error: unknown): boolean {
  return error instanceof ApiError && error.status === SLOT_CONFLICT;
}
