"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

/** Informational overview; navigation remains with the native scrollbar and transcript. */
export function TranscriptScrollReader({ children, revision }: { children: ReactNode; revision: string }) {
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

  return <div className="transcript-reader relative min-h-0 flex-1">
    <div ref={scroller} tabIndex={0} role="region" aria-label="Scrollable transcript" className="transcript-reader-scroll h-full overflow-y-scroll overscroll-y-contain pr-10 focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[var(--accent-strong)] sm:pr-16">
      {children}
    </div>
    <div aria-hidden="true" className="transcript-overview pointer-events-none absolute bottom-1 right-5 top-1 w-7 overflow-hidden border-l border-[var(--border)] sm:w-12">
      <div className="absolute inset-0 opacity-25 blur-[1px]">
        {overview.rows.map((row, index) => <span key={index} className="absolute left-1 h-px bg-[var(--text-muted)]" style={{ top: `${row.top}%`, width: `${row.width * .85}%` }} />)}
      </div>
      <div className="absolute inset-x-0 rounded-sm border border-[var(--border-strong)] bg-[var(--text-muted)]/10" style={{ top: `${overview.top}%`, height: `${overview.height}%` }} />
      {overview.rows.filter(row => row.proposed).map((row, index) => <span key={index} className="transcript-evidence-tick absolute inset-x-1 h-[3px] rounded-[1px]" style={{ top: `min(${row.top}%, calc(100% - 3px))` }} />)}
    </div>
  </div>;
}
