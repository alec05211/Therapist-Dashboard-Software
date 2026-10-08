type TextLoadingSkeletonProps = {
  className?: string;
  label?: string;
  widths?: string[];
};

/** Neutral loading copy that preserves the final text layout without exposing placeholder words. */
export function TextLoadingSkeleton({ className = "", label = "Loading content…", widths = ["94%", "86%", "68%"] }: TextLoadingSkeletonProps) {
  return <div role="status" aria-label={label} className={className}>
    <span className="sr-only">{label}</span>
    <div aria-hidden="true" className="grid gap-2.5">
      {widths.map((width, index) => <span key={`${width}-${index}`} className="text-loading-streak block" style={{ width }} />)}
    </div>
  </div>;
}

