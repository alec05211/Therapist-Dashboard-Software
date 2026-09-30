"use client";
import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import Image from "next/image";
import { LoadingSpinner } from "@/components/loading-spinner";
import { settingsFieldClass } from "@/components/settings-layout";

type ProfileRole = "therapist" | "client" | "client_pending" | "unregistered";
type Profile = { role: ProfileRole; name: string; firstName: string; lastName: string; pronouns: string | null; email: string | null; phone: string | null; aboutMe: string | null; discoverable: boolean | null; photoUrl: string | null };

export function AccountProfileForm() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [draft, setDraft] = useState<Profile | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [photoVersion, setPhotoVersion] = useState(0);
  useEffect(() => {
    let active = true;
    void fetch("/api/account/profile", { cache: "no-store" }).then(async response => {
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || "Could not load your profile.");
      if (active) { setProfile(body); setDraft(body); }
    }).catch((reason: Error) => { if (active) setError(reason.message); });
    return () => { active = false; };
  }, []);
  const update = (key: "name" | "firstName" | "lastName" | "pronouns" | "email" | "phone" | "aboutMe", value: string) => { setSaved(false); setDraft(current => current && ({ ...current, [key]: value })); };
  const save = async (event: FormEvent) => {
    event.preventDefault(); if (!draft || busy) return;
    setBusy(true); setError(null); setSaved(false);
    try {
      const name = draft.role === "therapist" ? draft.name : `${draft.firstName.trim()} ${draft.lastName.trim()}`.trim();
      const response = await fetch("/api/account/profile", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, first_name: draft.firstName, last_name: draft.lastName, pronouns: draft.pronouns || null, email: draft.email || null, phone: draft.phone || null, about_me: draft.role === "therapist" ? draft.aboutMe || null : null, discoverable: draft.discoverable }) });
      const body = await response.json(); if (!response.ok) throw new Error(body.detail || "Could not save your profile.");
      setProfile(body); setDraft(body); setSaved(true);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not save your profile."); }
    finally { setBusy(false); }
  };
  const upload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]; if (!file) return;
    if (file.size > 2 * 1024 * 1024 || !["image/jpeg", "image/png", "image/webp"].includes(file.type)) { setError("Choose a JPEG, PNG, or WebP image under 2 MB."); event.target.value = ""; return; }
    setBusy(true); setError(null); setSaved(false);
    try {
      const form = new FormData(); form.append("photo", file);
      const response = await fetch("/api/account/profile/photo", { method: "PUT", body: form });
      const body = await response.json(); if (!response.ok) throw new Error(body.detail || "Could not upload photo.");
      setProfile(current => current && ({ ...current, photoUrl: body.photoUrl })); setPhotoVersion(value => value + 1); setSaved(true);
      window.dispatchEvent(new Event("account-photo-changed"));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not upload photo."); }
    finally { setBusy(false); event.target.value = ""; }
  };
  const removePhoto = async () => {
    setBusy(true); setError(null); setSaved(false);
    try {
      const response = await fetch("/api/account/profile/photo", { method: "DELETE" });
      const body = await response.json(); if (!response.ok) throw new Error(body.detail || "Could not remove photo.");
      setProfile(current => current && ({ ...current, photoUrl: null })); setSaved(true);
      window.dispatchEvent(new Event("account-photo-changed"));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not remove photo."); }
    finally { setBusy(false); }
  };
  if (!draft) return error ? <p role="alert" className="mt-5 text-sm text-red-700">{error}</p> : <LoadingSpinner label="Loading profile…" />;
  return <form onSubmit={save} className="mt-6 space-y-5">
    <div className="flex flex-wrap items-center gap-4">
      <div className="relative grid size-20 shrink-0 place-items-center overflow-hidden rounded-full bg-emerald-800 text-xl font-semibold text-white">
        {profile?.photoUrl ? <Image src={`${profile.photoUrl}?v=${photoVersion}`} alt="Your profile photo" fill sizes="80px" unoptimized className="object-cover" /> : <span aria-hidden="true">{(draft.role === "therapist" ? draft.name : `${draft.firstName} ${draft.lastName}`).split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join("").toUpperCase()}</span>}
      </div>
      <div><label className="inline-flex cursor-grab rounded-lg border border-stone-300 px-3 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-50 active:cursor-grabbing">Upload photo<input type="file" accept="image/jpeg,image/png,image/webp" onChange={event => void upload(event)} disabled={busy} className="sr-only" /></label>
        {profile?.photoUrl && <button type="button" onClick={() => void removePhoto()} disabled={busy} className="ml-2 cursor-grab rounded-lg px-3 py-2 text-sm text-stone-600 hover:bg-stone-100 active:cursor-grabbing">Remove</button>}
        <p className="mt-1 text-xs text-stone-500">JPEG, PNG, or WebP · up to 2 MB</p></div>
    </div>
    {draft.role === "therapist" ? <label className="block text-sm font-semibold text-stone-800">Professional name<input required maxLength={200} value={draft.name} onChange={event => update("name", event.target.value)} className={settingsFieldClass} /><span className="mt-1 block text-xs font-normal text-stone-500">The name shown on your care profile.</span></label> : <div className="grid gap-4 sm:grid-cols-2"><label className="block text-sm font-semibold text-stone-800">First name<input required autoComplete="given-name" maxLength={100} value={draft.firstName} onChange={event => update("firstName", event.target.value)} className={settingsFieldClass} /></label><label className="block text-sm font-semibold text-stone-800">Last name<input required autoComplete="family-name" maxLength={100} value={draft.lastName} onChange={event => update("lastName", event.target.value)} className={settingsFieldClass} /></label></div>}
    <label className="block max-w-48 text-sm font-semibold text-stone-800">Pronouns<input maxLength={80} placeholder="e.g. she/her" value={draft.pronouns ?? ""} onChange={event => update("pronouns", event.target.value)} className={settingsFieldClass} /></label>
    <label className="block text-sm font-semibold text-stone-800">Email<input type="email" autoComplete="email" maxLength={254} value={draft.email ?? ""} onChange={event => update("email", event.target.value)} className={settingsFieldClass} /><span className="mt-1 block text-xs font-normal text-stone-500">Prefilled from your sign-in account and shown to people connected to your care profile.</span></label>
    <label className="block text-sm font-semibold text-stone-800">Contact phone<input type="tel" maxLength={40} value={draft.phone ?? ""} onChange={event => update("phone", event.target.value)} className={settingsFieldClass} /><span className="mt-1 block text-xs font-normal text-stone-500">Optional; leave blank to hide it from your profile.</span></label>
    {draft.role === "therapist" && <label className="block text-sm font-semibold text-stone-800">About me<textarea maxLength={2000} rows={5} value={draft.aboutMe ?? ""} onChange={event => update("aboutMe", event.target.value)} className={settingsFieldClass} /><span className="mt-1 block text-xs font-normal text-stone-500">A short introduction clients can read on your care profile.</span></label>}
    {(draft.role === "client_pending" || draft.role === "unregistered") && <label className="flex cursor-grab items-start justify-between gap-5 rounded-xl border border-stone-200 bg-stone-50 p-4 active:cursor-grabbing"><span><span className="block text-sm font-semibold text-stone-800">Let therapists find me</span><span className="mt-1 block text-xs leading-5 text-stone-500">Your name and contact email can appear when a therapist searches the client directory.</span></span><input type="checkbox" role="switch" checked={draft.discoverable !== false} onChange={event => { setSaved(false); setDraft(current => current && ({ ...current, discoverable: event.target.checked })); }} className="mt-0.5 size-5 cursor-grab accent-emerald-800 active:cursor-grabbing" /></label>}
    <div className="flex items-center gap-3 border-t border-stone-200 pt-5"><button disabled={busy} type="submit" className="cursor-grab rounded-lg bg-emerald-800 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-900 disabled:cursor-wait active:cursor-grabbing">{busy ? "Saving…" : "Save profile"}</button>{saved && <p role="status" className="text-sm font-medium text-emerald-800">Profile saved.</p>}</div>
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
  </form>;
}
