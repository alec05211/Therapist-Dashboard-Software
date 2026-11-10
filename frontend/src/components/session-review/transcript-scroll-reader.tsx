"use client";

import { useEffect, useId, useRef, useState, type ReactNode, type PointerEvent, type KeyboardEvent } from "react";

/** One scroll rail combines the transcript overview, evidence ticks, and navigation. */
export function TranscriptScrollReader({ children, revision }: { children: ReactNode; revision: string }) {
  const contentId = useId();
  const rail = useRef<HTMLDivElement>(null);
  const dragOffset = useRef<number | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const [overview, setOverview] = useState({ top: 0, height: 100, rows: [] as { top: number; width: number; proposed: boolean }[] });

  useEffect(() => {
    const element = scroller.current;
    if (!element) return;
    let frame = 0;
    const measure = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const bounds = element.getBoundingClientRect();
        const total = Math.max(element.scrollHeight, 1);
        setOverview({
          top: element.scrollTop / total * 100,
          height: element.clientHeight / total * 100,
          rows: Array.from(element.querySelectorAll<HTMLElement>("[data-transcript-segment]")).map(row => ({
            top: (row.getBoundingClientRect().top - bounds.top + element.scrollTop) / total * 100,
            width: Math.min(100, 25 + (row.textContent?.length ?? 0) / 3),
            proposed: row.dataset.proposed === "true",
          })),
        });
      });
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(element);
    if (element.firstElementChild) observer.observe(element.firstElementChild);
    element.addEventListener("scroll", measure, { passive: true });
    return () => { cancelAnimationFrame(frame); observer.disconnect(); element.removeEventListener("scroll", measure); };
  }, [revision]);

  useEffect(() => {
    const track = rail.current;
    if (!track) return;
    const wheel = (event: WheelEvent) => {
      event.preventDefault();
      const element = scroller.current;
      if (element) element.scrollTop += event.deltaY * (event.deltaMode === 1 ? 20 : event.deltaMode === 2 ? element.clientHeight : 1);
    };
    track.addEventListener("wheel", wheel, { passive: false });
    return () => track.removeEventListener("wheel", wheel);
  }, []);

  const moveTo = (event: PointerEvent<HTMLDivElement>) => {
    const element = scroller.current;
    const track = rail.current;
    if (!element || !track) return;
    const bounds = track.getBoundingClientRect();
    const fraction = (event.clientY - bounds.top - (dragOffset.current ?? 0)) / Math.max(bounds.height, 1);
    element.scrollTop = Math.max(0, Math.min(element.scrollHeight - element.clientHeight, fraction * element.scrollHeight));
  };
  const onRailKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const element = scroller.current;
    if (!element) return;
    const steps: Record<string, number> = { ArrowDown: 40, ArrowUp: -40, PageDown: element.clientHeight * .9, PageUp: -element.clientHeight * .9 };
    if (event.key in steps) { event.preventDefault(); element.scrollTop += steps[event.key]; }
    else if (event.key === "Home" || event.key === "End") { event.preventDefault(); element.scrollTop = event.key === "Home" ? 0 : element.scrollHeight; }
  };

  return <div className="transcript-reader relative min-h-0 flex-1">
    <div id={contentId} ref={scroller} tabIndex={0} role="region" aria-label="Scrollable transcript" className="transcript-reader-scroll h-full overflow-y-auto overscroll-y-contain pr-8 focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[var(--accent-strong)] sm:pr-12">
      {children}
    </div>
    <div ref={rail} role="scrollbar" tabIndex={0} aria-label="Transcript overview scroll bar" aria-controls={contentId} aria-orientation="vertical" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(overview.height >= 100 ? 0 : overview.top / (100 - overview.height) * 100)} onKeyDown={onRailKeyDown}
      onPointerDown={event => {
        if (event.button !== 0) return;
        event.preventDefault();
        event.currentTarget.focus({ preventScroll: true });
        event.currentTarget.setPointerCapture(event.pointerId);
        const bounds = event.currentTarget.getBoundingClientRect();
        const position = event.clientY - bounds.top;
        const top = overview.top / 100 * bounds.height;
        const height = overview.height / 100 * bounds.height;
        dragOffset.current = position >= top && position <= top + height ? position - top : height / 2;
        moveTo(event);
      }}
      onPointerMove={event => { if (dragOffset.current !== null) moveTo(event); }}
      onPointerUp={() => { dragOffset.current = null; }} onPointerCancel={() => { dragOffset.current = null; }} onLostPointerCapture={() => { dragOffset.current = null; }}
      className="transcript-overview absolute inset-y-0 right-0 w-7 touch-none cursor-grab overflow-hidden active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[var(--accent-strong)] sm:w-11">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0">
      <div className="absolute inset-0 opacity-25 blur-[1px]">
        {overview.rows.map((row, index) => <span key={index} className="absolute left-1 h-px bg-[var(--text-muted)]" style={{ top: `${row.top}%`, width: `${row.width * .85}%` }} />)}
      </div>
      <div className="absolute inset-x-0 rounded-sm border border-[var(--border-strong)] bg-[var(--text-muted)]/10" style={{ top: `${overview.top}%`, height: `${overview.height}%` }} />
      {overview.rows.filter(row => row.proposed).map((row, index) => <span key={index} className="transcript-evidence-tick absolute inset-x-1 h-[3px] rounded-[1px]" style={{ top: `min(${row.top}%, calc(100% - 3px))` }} />)}
      </div>
    </div>
  </div>;
}
