/** Lightweight cross-component signal so the header bell refreshes after bookings/status changes. */
const NOTIFICATIONS_CHANGED = 'medibook:notifications-changed';

export function emitNotificationsChanged(): void {
  window.dispatchEvent(new Event(NOTIFICATIONS_CHANGED));
}

export function onNotificationsChanged(handler: () => void): () => void {
  window.addEventListener(NOTIFICATIONS_CHANGED, handler);
  return () => window.removeEventListener(NOTIFICATIONS_CHANGED, handler);
}
