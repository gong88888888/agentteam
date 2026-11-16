// Suppress late results even when the transport ignores AbortSignal.
export function createLatestTask() {
  let generation = 0;
  let controller;
  let disposed = false;
  function cancel() {
    generation += 1;
    controller?.abort();
    controller = undefined;
  }
  return {
    cancel,
    dispose() { disposed = true; cancel(); },
    async run(work) {
      if (disposed) throw new Error('Task is disposed');
      cancel();
      const current = generation;
      const active = new AbortController();
      controller = active;
      try {
        const value = await work(active.signal);
        return current === generation
          ? { status: 'success', value }
          : { status: 'discarded' };
      } catch (error) {
        if (current !== generation) return { status: 'discarded' };
        throw error;
      } finally {
        if (controller === active) controller = undefined;
      }
    }
  };
}

export function createObjectUrlPool(api = globalThis.URL) {
  const urls = new Set();
  let disposed = false;
  function release(url) {
    if (urls.delete(url)) api.revokeObjectURL(url);
  }
  function clear() { for (const url of urls) release(url); }
  return {
    create(blob) {
      if (disposed) throw new Error('URL pool is disposed');
      const url = api.createObjectURL(blob);
      urls.add(url);
      return url;
    },
    release,
    clear,
    dispose() { clear(); disposed = true; },
    get size() { return urls.size; }
  };
}

// Diagnostic candidates, not a complete visual/accessibility audit.
export function inspectOverflow(root = document.documentElement, tolerance = 1) {
  return [root, ...root.querySelectorAll('*')].flatMap(element => {
    if (!element.getClientRects().length || element.clientWidth === 0) return [];
    const excess = element.scrollWidth - element.clientWidth;
    if (excess <= tolerance) return [];
    const style = element.ownerDocument.defaultView.getComputedStyle(element);
    const scrollable = /^(auto|scroll)$/.test(style.overflowX);
    const reason = element.getAttribute('data-af-scroll-reason');
    return [{
      element: element.id ? `#${element.id}` : element.tagName.toLowerCase(),
      width: element.clientWidth,
      scrollWidth: element.scrollWidth,
      overflowX: style.overflowX,
      expected: scrollable && Boolean(reason?.trim()),
      reason: reason || null
    }];
  });
}
