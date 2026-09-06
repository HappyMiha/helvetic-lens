// Native overlays can overlap during a handoff. Restore each original style only
// after the final owner releases it, regardless of which overlay closes first.
const locks = new Map<HTMLElement, { count: number; overflow: string }>();

export function lockOverlayScroll() {
  const elements = [
    document.documentElement,
    document.querySelector<HTMLElement>("main.main"),
  ].filter((element): element is HTMLElement => Boolean(element));
  for (const element of elements) {
    const lock = locks.get(element);
    if (lock) lock.count += 1;
    else {
      locks.set(element, { count: 1, overflow: element.style.overflow });
      element.style.overflow = "hidden";
    }
  }
  let released = false;
  return () => {
    if (released) return;
    released = true;
    for (const element of elements) {
      const lock = locks.get(element);
      if (!lock || --lock.count > 0) continue;
      element.style.overflow = lock.overflow;
      locks.delete(element);
    }
  };
}
