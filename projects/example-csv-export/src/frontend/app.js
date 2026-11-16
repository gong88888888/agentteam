export function exportState(status) {
  return { ready: status === 'ready', loading: status === 'loading' };
}
