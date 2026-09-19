export function LoadingSpinner({ label = "Loading…" }: { label?: string }) {
  return <div role="status" className="flex items-center justify-center gap-3 py-6 text-sm text-stone-600">
    <span aria-hidden="true" className="size-5 shrink-0 animate-spin rounded-full border-2 border-stone-300 border-t-emerald-700 motion-reduce:animate-none" />
    <span>{label}</span>
  </div>;
}
