"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import { canUseFeature } from "@/lib/role-capabilities";

function Icon({ children }: { children: ReactNode }) {
  return <svg aria-hidden="true" className="size-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.2">{children}</svg>;
}

function UserIcon() { return <Icon><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 6.75a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM4.5 20.1a7.5 7.5 0 0 1 15 0" /></Icon>; }
function CloseIcon() { return <Icon><path strokeLinecap="round" strokeLinejoin="round" d="m6 6 12 12M18 6 6 18" /></Icon>; }
function CalendarIcon() { return <Icon><path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3v3m10.5-3v3M4.5 9.75h15M5.63 4.5h12.74c.62 0 1.13.5 1.13 1.13v12.74c0 .62-.5 1.13-1.13 1.13H5.63c-.62 0-1.13-.5-1.13-1.13V5.63c0-.62.5-1.13 1.13-1.13Z" /></Icon>; }
function ClientsIcon() { return <Icon><path strokeLinecap="round" strokeLinejoin="round" d="M15 19.13a6.76 6.76 0 0 0-6 0M15.75 6.75a3.75 3.75 0 1 1-7.5 0 3.75 3.75 0 0 1 7.5 0ZM20.25 19.13a6.76 6.76 0 0 0-2.74-2.28M18 5.1a3.75 3.75 0 0 1 0 6.9M3.75 19.13a6.76 6.76 0 0 1 2.74-2.28M6 5.1a3.75 3.75 0 0 0 0 6.9" /></Icon>; }
function PracticeIcon() { return <Icon><path strokeLinecap="round" strokeLinejoin="round" d="M3.75 20.25h16.5M5.25 20.25V7.5L12 3.75l6.75 3.75v12.75M9 20.25v-4.5h6v4.5M8.25 9.75h.01M12 9.75h.01M15.75 9.75h.01" /></Icon>; }
function BillingIcon() { return <Icon><path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3.75h10.5c.83 0 1.5.67 1.5 1.5v13.5c0 .83-.67 1.5-1.5 1.5H6.75c-.83 0-1.5-.67-1.5-1.5V5.25c0-.83.67-1.5 1.5-1.5ZM8.25 8.25h7.5m-7.5 3h7.5m-7.5 3h3" /></Icon>; }
function DocumentsIcon() { return <Icon><path strokeLinecap="round" strokeLinejoin="round" d="M6.75 3.75h7.5l3 3v13.5H6.75V3.75Z" /><path strokeLinecap="round" strokeLinejoin="round" d="M14.25 3.75v3h3M9 11.25h6m-6 3h6m-6 3h3.75" /></Icon>; }
function SettingsIcon() { return <Icon><path strokeLinecap="round" strokeLinejoin="round" d="M10.3 4.32a1.65 1.65 0 0 1 3.4 0l.16.9a1.65 1.65 0 0 0 2.48 1.17l.78-.47a1.65 1.65 0 0 1 2.4 2.4l-.47.78a1.65 1.65 0 0 0 1.17 2.48l.9.16a1.65 1.65 0 0 1 0 3.4l-.9.16a1.65 1.65 0 0 0-1.17 2.48l.47.78a1.65 1.65 0 0 1-2.4 2.4l-.78-.47a1.65 1.65 0 0 0-2.48 1.17l-.16.9a1.65 1.65 0 0 1-3.4 0l-.16-.9a1.65 1.65 0 0 0-2.48-1.17l-.78.47a1.65 1.65 0 0 1-2.4-2.4l.47-.78a1.65 1.65 0 0 0-1.17-2.48l-.9-.16a1.65 1.65 0 0 1 0-3.4l.9-.16A1.65 1.65 0 0 0 5.2 8.66l-.47-.78a1.65 1.65 0 0 1 2.4-2.4l.78.47a1.65 1.65 0 0 0 2.48-1.17l.16-.9Z" /><path strokeLinecap="round" strokeLinejoin="round" d="M15 12a3 3 0 1 1-6 0 3 3 0 0 1 6 0Z" /></Icon>; }
function InboxIcon() { return <Icon><path strokeLinecap="round" strokeLinejoin="round" d="M14.25 18.75a2.25 2.25 0 0 1-4.5 0m8.25-7.5a6 6 0 0 0-12 0c0 7.5-3 6-3 7.5h18c0-1.5-3 0-3-7.5Z" /></Icon>; }
function LogoutIcon() { return <Icon><path strokeLinecap="round" strokeLinejoin="round" d="M15.75 8.25V5.63c0-.62-.5-1.13-1.13-1.13H5.63c-.62 0-1.13.5-1.13 1.13v12.74c0 .62.5 1.13 1.13 1.13h8.99c.62 0 1.13-.5 1.13-1.13v-2.62M12 12h7.5m0 0-3-3m3 3-3 3" /></Icon>; }

type AccountRole = "therapist" | "client";
type MenuLinkProps = { href: string; label: string; icon: ReactNode; active: boolean; badge?: number; onSelect: () => void };

function MenuLink({ href, label, icon, active, badge, onSelect }: MenuLinkProps) {
  return <Link href={href} onClick={onSelect} aria-current={active ? "page" : undefined} className={`group flex min-h-11 w-full cursor-grab items-center justify-start pl-12 pr-3 py-2 text-left text-base font-medium transition-[color,transform,font-size] duration-200 ease-out focus-visible:rounded-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing ${active ? "scale-[1.025] text-emerald-800" : "text-stone-800 hover:scale-[1.025] hover:text-emerald-800"}`}>
    <span className="relative grid grid-cols-[1.75rem_auto] items-center gap-2.5"><span className="grid size-7 place-items-center">{icon}</span><span>{label}</span>{badge ? <span className="absolute -right-7 grid min-h-5 min-w-5 place-items-center rounded-full bg-emerald-800 px-1.5 text-[10px] font-bold text-white">{badge > 9 ? "9+" : badge}</span> : null}</span>
  </Link>;
}

function DisabledMenuItem({ label, icon }: { label: string; icon: ReactNode }) {
  return <button disabled type="button" className="flex min-h-11 w-full cursor-not-allowed items-center justify-start pl-12 pr-3 py-2 text-left text-base font-medium text-stone-500 opacity-55">
    <span className="grid grid-cols-[1.75rem_auto] items-center gap-2.5"><span className="grid size-7 place-items-center">{icon}</span><span>{label}</span></span>
  </button>;
}

export function AppHeader() {
  const pathname = usePathname();
  const [isOpen, setIsOpen] = useState(false);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean | null>(null);
  const [accountRole, setAccountRole] = useState<AccountRole | null>(null);
  const [accountName, setAccountName] = useState("Account");
  const [photoUrl, setPhotoUrl] = useState<string | null>(null);
  const [unreadCount, setUnreadCount] = useState(0);
  const menuId = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    void fetch("/api/auth-status", { cache: "no-store" }).then(response => response.json()).then((body: { authenticated?: boolean }) => {
      const authenticated = Boolean(body.authenticated);
      setIsAuthenticated(authenticated);
      if (!authenticated) return;
      void fetch("/api/identity/me", { cache: "no-store" }).then(response => response.json()).then((identity: { role?: string; displayName?: string }) => {
        if (identity.role === "therapist" || identity.role === "client") setAccountRole(identity.role);
        if (identity.displayName) setAccountName(identity.displayName);
      });
    }).catch(() => setIsAuthenticated(false));
  }, []);

  useEffect(() => {
    if (!isAuthenticated) return;
    let controller: AbortController;
    const refreshPhoto = () => {
      controller?.abort();
      controller = new AbortController();
      const signal = controller.signal;
      void fetch("/api/account/profile", { cache: "no-store", signal }).then(async response => {
        if (!response.ok) throw new Error("Profile unavailable");
        const profile = await response.json();
        if (!signal.aborted) setPhotoUrl(profile.photoUrl ? `${profile.photoUrl}?v=${Date.now()}` : null);
      }).catch(() => { if (!signal.aborted) setPhotoUrl(null); });
    };
    refreshPhoto();
    window.addEventListener("account-photo-changed", refreshPhoto);
    return () => { controller.abort(); window.removeEventListener("account-photo-changed", refreshPhoto); };
  }, [isAuthenticated]);

  useEffect(() => {
    if (!isAuthenticated) return;
    const refreshInbox = () => { void fetch("/api/inbox", { cache: "no-store" }).then(response => response.ok ? response.json() : null).then(body => setUnreadCount(body?.unreadCount || 0)).catch(() => setUnreadCount(0)); };
    refreshInbox();
    window.addEventListener("inbox-changed", refreshInbox);
    return () => window.removeEventListener("inbox-changed", refreshInbox);
  }, [isAuthenticated]);

  useEffect(() => {
    if (!isOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") { setIsOpen(false); triggerRef.current?.focus(); }
    };
    document.addEventListener("keydown", closeOnEscape);
    return () => { document.body.style.overflow = previousOverflow; document.removeEventListener("keydown", closeOnEscape); };
  }, [isOpen]);

  const showTherapistNavigation = Boolean(isAuthenticated && accountRole && canUseFeature(accountRole, "practiceNavigation"));
  const closeMenu = () => setIsOpen(false);
  const accountImage = photoUrl && isAuthenticated
    ? <Image key={photoUrl} src={photoUrl} alt="" fill sizes="48px" unoptimized className="rounded-full object-cover" onError={() => setPhotoUrl(null)} />
    : <UserIcon />;

  return <>
    <header className="relative z-40 border-b border-stone-200 bg-white">
      <div className="mx-auto flex min-h-16 w-[min(94vw,1400px)] items-center justify-between gap-4 py-2">
        <Link className="cursor-grab whitespace-nowrap text-lg font-semibold tracking-tight text-stone-900 active:cursor-grabbing" href="/">Therapist Dashboard</Link>
        <button ref={triggerRef} aria-controls={menuId} aria-expanded={isOpen} aria-haspopup="dialog" aria-label={isOpen ? "Close navigation menu" : "Open account and navigation menu"} className={`relative inline-flex size-10 cursor-grab items-center justify-center rounded-full border border-stone-300 bg-white text-stone-700 shadow-sm transition-colors duration-200 ease-out motion-reduce:transition-none hover:bg-stone-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing ${isOpen ? "pointer-events-none" : ""}`} onClick={() => setIsOpen(true)} type="button">
          {accountImage}
          {unreadCount > 0 && !isOpen ? <span className="absolute -right-1 -top-1 grid min-h-5 min-w-5 place-items-center rounded-full bg-emerald-800 px-1 text-[10px] font-bold text-white">{unreadCount > 9 ? "9+" : unreadCount}</span> : null}
        </button>
      </div>
    </header>

    <div id={menuId} role="dialog" aria-modal="true" aria-label="Account and navigation menu" aria-hidden={!isOpen} inert={!isOpen} className={`fixed inset-0 z-50 bg-stone-950/20 backdrop-blur-[5px] transition-[opacity,visibility] duration-200 ease-out motion-reduce:transition-none ${isOpen ? "visible opacity-100" : "invisible pointer-events-none opacity-0 delay-300"}`} onMouseDown={(event) => { if (event.target === event.currentTarget) { closeMenu(); triggerRef.current?.focus(); } }}>
      <aside style={{ right: "calc(max(3vw, calc((100vw - 1400px) / 2)) - 12px)" }} className={`absolute top-0 max-h-[calc(100vh-0.75rem)] origin-top-right overflow-hidden rounded-2xl border border-stone-300 bg-white shadow-2xl transition-[width] duration-[560ms] ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none ${isOpen ? "w-[min(97vw,442px)]" : "w-16"}`}>
        <div className={`relative shrink-0 transition-[height] duration-[560ms] ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none ${isOpen ? "h-[4.25rem]" : "h-16"}`}>
          <div className={`absolute top-3 flex h-10 min-w-0 items-center overflow-hidden transition-[width,right] duration-[560ms] ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none ${isOpen ? "right-16 w-[calc(100%-5rem)]" : "right-3 w-10"}`}>
            <span className="relative grid size-10 shrink-0 place-items-center overflow-hidden rounded-full border border-stone-300 bg-stone-100 text-stone-700">{accountImage}</span>
            <span className={`ml-3 min-w-0 whitespace-nowrap transition-[opacity,transform] delay-150 duration-300 ease-out motion-reduce:transition-none ${isOpen ? "translate-x-0 opacity-100" : "translate-x-4 opacity-0"}`}><span className="block truncate text-sm font-semibold text-stone-900">{isAuthenticated ? accountName : "Welcome"}</span><span className="block text-xs capitalize text-stone-600">{isAuthenticated ? `${accountRole ?? "member"} account` : "Not signed in"}</span></span>
          </div>
          <button ref={closeRef} type="button" onClick={() => { closeMenu(); triggerRef.current?.focus(); }} className={`absolute right-3 top-3 inline-flex size-10 cursor-grab items-center justify-center rounded-full border border-stone-300 bg-stone-100 text-stone-700 transition-[opacity,transform,background-color] delay-100 duration-300 ease-out motion-reduce:transition-none hover:bg-stone-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing ${isOpen ? "rotate-0 opacity-100" : "rotate-90 opacity-0"}`} aria-label="Close navigation menu"><CloseIcon /></button>
        </div>

        <div className={`grid transition-[grid-template-rows] duration-[560ms] ease-[cubic-bezier(0.22,1,0.36,1)] motion-reduce:transition-none ${isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"}`}>
          <div className="min-h-0 overflow-hidden">
            <div className={`max-h-[calc(100vh-5rem)] overflow-y-auto border-t border-stone-200 transition-opacity duration-300 ease-out motion-reduce:transition-none ${isOpen ? "opacity-100 delay-100" : "opacity-0"}`}>
              <div className="p-3">
                {showTherapistNavigation ? <nav aria-label="Therapist workspace" className="space-y-0.5 text-left">
                  <MenuLink href="/inbox" label="Inbox" icon={<InboxIcon />} badge={unreadCount} active={pathname.startsWith("/inbox")} onSelect={closeMenu} />
                  <MenuLink href="/clients" label="Client list" icon={<ClientsIcon />} active={pathname.startsWith("/clients")} onSelect={closeMenu} />
                  <MenuLink href="/calendar" label="Calendar" icon={<CalendarIcon />} active={pathname.startsWith("/calendar")} onSelect={closeMenu} />
                  <MenuLink href="/practice" label="Practice" icon={<PracticeIcon />} active={pathname.startsWith("/practice")} onSelect={closeMenu} />
                  <DisabledMenuItem label="Billing" icon={<BillingIcon />} />
                  <DisabledMenuItem label="Documents" icon={<DocumentsIcon />} />
                  <MenuLink href="/settings?section=appearance" label="Settings" icon={<SettingsIcon />} active={pathname.startsWith("/settings")} onSelect={closeMenu} />
                </nav> : isAuthenticated ? <nav aria-label="Account navigation" className="space-y-0.5 text-left">
                  <MenuLink href="/inbox" label="Inbox" icon={<InboxIcon />} badge={unreadCount} active={pathname.startsWith("/inbox")} onSelect={closeMenu} />
                  <MenuLink href="/settings?section=profile" label="Settings" icon={<SettingsIcon />} active={pathname.startsWith("/settings")} onSelect={closeMenu} />
                </nav> : <a href="/login" className="flex min-h-12 cursor-grab items-center gap-3 rounded-xl border border-emerald-700 bg-emerald-50 px-4 py-3 text-base font-semibold text-emerald-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing"><span className="grid size-7 place-items-center"><UserIcon /></span>Sign in</a>}
              </div>
              {isAuthenticated ? <div className="border-t border-stone-200 p-3"><a className="group flex min-h-11 cursor-grab items-center justify-start pl-12 pr-3 py-2 text-left text-sm font-medium text-stone-600 transition-[color,transform] duration-200 ease-out hover:scale-[1.025] hover:text-emerald-800 focus-visible:rounded-lg focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700 active:cursor-grabbing" href="/auth/logout"><span className="grid grid-cols-[1.75rem_auto] items-center gap-2.5"><span className="grid size-7 place-items-center"><LogoutIcon /></span><span>Log out</span></span></a></div> : null}
            </div>
          </div>
        </div>
      </aside>
    </div>
  </>;
}
