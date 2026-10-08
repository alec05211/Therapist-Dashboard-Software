"use client";

import { useId, useState, type ReactNode } from "react";

type Props = {
  title: string;
  preview: string;
  previewContent?: ReactNode;
  children: ReactNode;
  summary?: ReactNode;
  ariaLabel?: string;
  className?: string;
  expanded?: boolean;
  onExpandedChange?: (expanded: boolean) => void;
  headerCenter?: ReactNode;
  headerActions?: ReactNode;
  keepMounted?: boolean;
  collapsedPreviewHeight?: number;
};

/** Shared compact text preview and disclosure shell; expanded content owns its controls. */
export function CollapsibleContentPanel({ title, preview, previewContent, children, summary, ariaLabel, className = "", expanded: controlledExpanded, onExpandedChange, headerCenter, headerActions, keepMounted = false, collapsedPreviewHeight = 96 }: Props) {
  const [internalExpanded, setInternalExpanded] = useState(false);
  const expanded = controlledExpanded ?? internalExpanded;
  const contentId = useId();
  const toggle = () => {
    if (controlledExpanded === undefined) setInternalExpanded(!expanded);
    onExpandedChange?.(!expanded);
  };
  return <section className={`relative overflow-hidden rounded-xl border border-stone-200 bg-stone-100 text-stone-900 ${className}`} aria-label={ariaLabel ?? title}>
    <div className="relative">
      <div className="p-4">
        <span className="flex flex-wrap items-baseline gap-x-2 gap-y-1 pr-6"><span className="text-base font-semibold">{title}</span>{summary && <span className="text-sm text-stone-600">{summary}</span>}</span>
        {!expanded && !previewContent && <span className="collapsed-content-preview mt-3 block overflow-hidden text-sm leading-6 text-stone-600" style={{ height: collapsedPreviewHeight }}>{preview}</span>}
      </div>
      {!expanded && previewContent && <>
        <span className="sr-only">{preview}</span>
        <div className="collapsed-content-preview overflow-hidden" style={{ height: collapsedPreviewHeight }} inert aria-hidden="true">{previewContent}</div>
      </>}
      {headerCenter && <div className="absolute left-1/2 top-2.5 z-20 flex -translate-x-1/2 items-center">{headerCenter}</div>}
      {headerActions && <div className="absolute right-12 top-2.5 z-20 flex items-center gap-2">{headerActions}</div>}
      <button type="button" onClick={toggle} aria-label={title} aria-expanded={expanded} aria-controls={contentId} className="absolute inset-0 z-10 w-full cursor-grab rounded-xl text-left transition-colors duration-200 ease-out hover:bg-stone-200/20 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-emerald-700">
        <span className={`absolute right-3 grid size-7 place-items-center rounded-full border border-stone-200 bg-stone-100 text-stone-700 shadow-sm ${expanded ? "top-3" : "bottom-3"}`} aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={`size-4 ${expanded ? "rotate-180" : ""}`}><path d="m6 9 6 6 6-6" /></svg>
        </span>
      </button>
    </div>
    <div id={contentId} hidden={!expanded}>{expanded || keepMounted ? children : null}</div>
  </section>;
}
