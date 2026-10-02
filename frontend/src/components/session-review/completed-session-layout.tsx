import type { ReactNode } from "react";

type CompletedSessionLayoutProps = {
  children: ReactNode;
};

export function CompletedSessionLayout({ children }: CompletedSessionLayoutProps) {
  return <section aria-label="Completed session review">{children}</section>;
}
