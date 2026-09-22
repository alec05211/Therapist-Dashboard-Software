"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { canUseFeature } from "@/lib/role-capabilities";
import { useEffect, useId, useRef, useState } from "react";

function GearIcon() {
  return (
    <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M10.3 4.32a1.65 1.65 0 0 1 3.4 0l.16.9a1.65 1.65 0 0 0 2.48 1.17l.78-.47a1.65 1.65 0 0 1 2.4 2.4l-.47.78a1.65 1.65 0 0 0 1.17 2.48l.9.16a1.65 1.65 0 0 1 0 3.4l-.9.16a1.65 1.65 0 0 0-1.17 2.48l.47.78a1.65 1.65 0 0 1-2.4 2.4l-.78-.47a1.65 1.65 0 0 0-2.48 1.17l-.16.9a1.65 1.65 0 0 1-3.4 0l-.16-.9a1.65 1.65 0 0 0-2.48-1.17l-.78.47a1.65 1.65 0 0 1-2.4-2.4l.47-.78a1.65 1.65 0 0 0-1.17-2.48l-.9-.16a1.65 1.65 0 0 1 0-3.4l.9-.16A1.65 1.65 0 0 0 5.2 8.66l-.47-.78a1.65 1.65 0 0 1 2.4-2.4l.78.47a1.65 1.65 0 0 0 2.48-1.17l.16-.9Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" />
    </svg>
  );
}

function UserIcon() {
  return (
    <svg aria-hidden="true" className="size-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6.75a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.5 20.1a7.5 7.5 0 0 1 15 0" />
    </svg>
  );
}

function LogoutIcon() {
  return (
    <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15.75 8.25V5.63c0-.62-.5-1.13-1.13-1.13H5.63c-.62 0-1.13.5-1.13 1.13v12.74c0 .62.5 1.13 1.13 1.13h8.99c.62 0 1.13-.5 1.13-1.13v-2.62M12 12h7.5m0 0-3-3m3 3-3 3" />
    </svg>
  );
}

function CalendarIcon() {
  return (
    <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v3m10.5-3v3M4.5 9.75h15M5.63 4.5h12.74c.62 0 1.13.5 1.13 1.13v12.74c0 .62-.5 1.13-1.13 1.13H5.63c-.62 0-1.13-.5-1.13-1.13V5.63c0-.62.5-1.13 1.13-1.13Z" />
    </svg>
  );
}

function ClientsIcon() {
  return (
    <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M15 19.13a6.76 6.76 0 0 0-6 0M15.75 6.75a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM20.25 19.13a6.76 6.76 0 0 0-2.74-2.28M18 5.1a3.75 3.75 0 0 1 0 6.9M3.75 19.13a6.76 6.76 0 0 1 2.74-2.28M6 5.1a3.75 3.75 0 0 0 0 6.9" />
    </svg>
  );
}

function PracticeIcon() {
  return (
    <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 20.25h16.5M5.25 20.25V7.5L12 3.75l6.75 3.75v12.75M9 20.25v-4.5h6v4.5M8.25 9.75h.01M12 9.75h.01M15.75 9.75h.01" />
    </svg>
  );
}

function BillingIcon() {
  return (
    <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3.75h10.5c.83 0 1.5.67 1.5 1.5v13.5c0 .83-.67 1.5-1.5 1.5H6.75c-.83 0-1.5-.67-1.5-1.5V5.25c0-.83.67-1.5 1.5-1.5ZM8.25 8.25h7.5m-7.5 3h7.5m-7.5 3h3" />
    </svg>
  );
}

function DocumentsIcon() {
  return (
    <svg aria-hidden="true" className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="1.8">
      <path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3.75h7.5l3 3v13.5H6.75V3.75Z" />
      <path strokeLinecap="round" strokeLinejoin="round" d="M14.25 3.75v3h3M9 11.25h6m-6 3h6m-6 3h3.75" />
    </svg>
  );
}

export function AppHeader() {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [accountRole, setAccountRole] = useState<"therapist" | "client" | null>(null);
  const menuId = useId();
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function closeOnOutsideInteraction(event: MouseEvent) {
      if (!menuRef.current?.contains(event.target as Node)) setIsOpen(false);
    }

    function closeOnEscape(event: KeyboardEvent) {
      if (event.key === "Escape") setIsOpen(false);
    }

    document.addEventListener("mousedown", closeOnOutsideInteraction);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("mousedown", closeOnOutsideInteraction);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, []);

  useEffect(() => {
    void fetch("/api/auth-status", { cache: "no-store" })
      .then((response) => response.json())
      .then((body: { authenticated?: boolean }) => { setIsAuthenticated(Boolean(body.authenticated)); if (body.authenticated) void fetch("/api/identity/me", { cache: "no-store" }).then(response => response.json()).then(identity => { if (identity.role === "therapist" || identity.role === "client") setAccountRole(identity.role); }); })
      .catch(() => setIsAuthenticated(false));
  }, []);

  return (
    <header className="border-b border-stone-200 bg-white">
      <div className="mx-auto flex h-16 w-[min(94vw,1200px)] items-center justify-between">
        <Link className="text-lg font-semibold tracking-tight text-stone-900" href="/">
          Therapist Dashboard
        </Link>
        <nav className="flex items-center" aria-label="Account navigation">
          <div className="relative" ref={menuRef}>
            <button
              aria-controls={menuId}
              aria-expanded={isOpen}
              aria-haspopup="menu"
              className="inline-flex size-10 cursor-grab items-center justify-center rounded-full border border-stone-300 bg-white text-stone-700 shadow-sm hover:bg-stone-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing"
              onClick={() => setIsOpen((open) => !open)}
              type="button"
            >
              <span className="sr-only">Open account menu</span>
              <UserIcon />
            </button>
            {isOpen && (
              <div id={menuId} className="absolute right-0 z-10 mt-2 w-52 rounded-xl border border-stone-200 bg-white p-1.5 shadow-lg">
                {isAuthenticated ? <><Link
                  className="flex w-full cursor-grab items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-stone-700 hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing"
                  href="/settings?section=profile"
                  onClick={() => setIsOpen(false)}
                ><GearIcon />Account settings</Link><div className="my-1 border-t border-stone-100" /><a
                  className="flex w-full cursor-grab items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-stone-700 hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing"
                  href="/auth/logout"
                ><LogoutIcon />Log out</a></> : <a
                  className="flex w-full cursor-grab items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-stone-700 hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing"
                  href="/login"
                ><UserIcon />Sign in</a>}
              </div>
            )}
          </div>
        </nav>
      </div>
      {isAuthenticated && accountRole && canUseFeature(accountRole, "practiceNavigation") && <div className="border-t border-stone-100 bg-stone-50">
        <nav className="mx-auto flex min-h-12 w-[min(94vw,1200px)] flex-wrap items-center justify-end gap-2 py-1" aria-label="Therapist workspace">
          <button
            aria-disabled="true"
            className="inline-flex cursor-not-allowed items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-stone-500"
            title="Calendar is coming soon"
            type="button"
          >
            <CalendarIcon />
            Calendar
            <span className="rounded-full bg-stone-200 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-stone-500">Soon</span>
          </button>
          <Link
            href="/clients"
            aria-current={pathname.startsWith("/clients") ? "page" : undefined}
            className={`inline-flex cursor-grab items-center gap-2 rounded-xl border px-3 py-2 text-sm font-medium transition-colors duration-200 hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing ${pathname.startsWith("/clients") ? "border-emerald-700 bg-emerald-50 text-emerald-800" : "border-transparent text-stone-700"}`}
          >
            <ClientsIcon />
            Client list
          </Link>
          <button
            aria-disabled="true"
            className="inline-flex cursor-not-allowed items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-stone-500"
            title="Practice settings are coming soon"
            type="button"
          >
            <PracticeIcon />
            Practice
            <span className="rounded-full bg-stone-200 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-stone-500">Soon</span>
          </button>
          <button
            aria-disabled="true"
            className="inline-flex cursor-not-allowed items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-stone-500"
            title="Billing is coming soon"
            type="button"
          >
            <BillingIcon />
            Billing
            <span className="rounded-full bg-stone-200 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-stone-500">Soon</span>
          </button>
          <button
            aria-disabled="true"
            className="inline-flex cursor-not-allowed items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-stone-500"
            title="Documents are coming soon"
            type="button"
          >
            <DocumentsIcon />
            Documents
            <span className="rounded-full bg-stone-200 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-stone-500">Soon</span>
          </button>
          <Link
            className="inline-flex cursor-grab items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium text-stone-700 hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing"
            href="/settings?section=appearance"
          >
            <GearIcon />
            Settings
          </Link>
        </nav>
      </div>}
    </header>
  );
}
