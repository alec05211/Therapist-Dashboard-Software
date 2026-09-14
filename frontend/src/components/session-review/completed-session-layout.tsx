import type { ReactNode } from "react";

type CompletedSessionLayoutProps = {
  children: ReactNode;
  sessionId: string;
};

export function CompletedSessionLayout({ children, sessionId }: CompletedSessionLayoutProps) {
  return (
    <section aria-label="Completed session review">
      <div className="mb-3 flex items-baseline gap-2">
        <h2 className="text-base font-semibold text-stone-900">Completed Session</h2>
        <span className="text-sm text-stone-600">{sessionId}</span>
      </div>
      {children}
    </section>
  );
}
