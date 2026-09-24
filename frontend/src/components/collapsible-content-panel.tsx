"use client";

import { useId, useState, type ReactNode } from "react";

type Props = {
  title: string;
  preview: string;
  children: ReactNode;
  summary?: string;
  ariaLabel?: string;
  className?: string;
  expanded?: boolean;
  onExpandedChange?: (expanded: boolean) => void;
};

/** Shared compact text preview and disclosure shell; expanded content owns its controls. */
export function CollapsibleContentPanel({ title, preview, children, summary, ariaLabel, className = "", expanded: controlledExpanded, onExpandedChange }: Props) {
  const [internalExpanded, setInternalExpanded] = useState(false);
  const expanded = controlledExpanded ?? internalExpanded;
  const contentId = useId();
  const toggle = () => {
    if (controlledExpanded === undefined) setInternalExpanded(!expanded);
    onExpandedChange?.(!expanded);
  };
  return <section className={`relative overflow-hidden rounded-xl border border-stone-200 bg-stone-100 text-stone-900 ${className}`} aria-label={ariaLabel ?? title}>
    <button type="button" onClick={toggle} aria-label={title} aria-expanded={expanded} aria-controls={contentId} className="relative block w-full cursor-grab p-4 text-left transition-colors duration-200 ease-out hover:bg-stone-200 active:cursor-grabbing focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-emerald-700">
      <span className="flex flex-wrap items-baseline gap-x-2 gap-y-1 pr-6"><span className="text-base font-semibold">{title}</span>{summary && <span className="text-sm text-stone-600">{summary}</span>}</span>
      {!expanded && <span className="collapsed-content-preview mt-3 block h-24 overflow-hidden text-sm leading-6 text-stone-600">{preview}</span>}
      <span className={`absolute right-4 text-lg text-stone-600 ${expanded ? "top-3" : "bottom-3"}`} aria-hidden="true">{expanded ? "⌃" : "⌄"}</span>
    </button>
    <div id={contentId} hidden={!expanded}>{expanded ? children : null}</div>
  </section>;
}
