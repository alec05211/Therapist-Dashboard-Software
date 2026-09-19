"use client";
import { useEffect, useState, type ChangeEvent, type FormEvent } from "react";
import Image from "next/image";
import { LoadingSpinner } from "@/components/loading-spinner";
import { canUseFeature, type AccountRole } from "@/lib/role-capabilities";

type Profile = { role: AccountRole; name: string; email: string | null; phone: string | null; aboutMe: string | null; photoUrl: string | null };
const fieldClass = "mt-1 block w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-700";

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
  const update = (key: "name" | "email" | "phone" | "aboutMe", value: string) => { setSaved(false); setDraft(current => current && ({ ...current, [key]: value })); };
  const save = async (event: FormEvent) => {
    event.preventDefault(); if (!draft || busy) return;
    setBusy(true); setError(null); setSaved(false);
    try {
      const response = await fetch("/api/account/profile", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: draft.name, email: draft.email || null, phone: draft.phone || null, about_me: canUseFeature(draft.role, "aboutMe") ? draft.aboutMe || null : null }) });
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
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not upload photo."); }
    finally { setBusy(false); event.target.value = ""; }
  };
  const removePhoto = async () => {
    setBusy(true); setError(null); setSaved(false);
    try {
      const response = await fetch("/api/account/profile/photo", { method: "DELETE" });
      const body = await response.json(); if (!response.ok) throw new Error(body.detail || "Could not remove photo.");
      setProfile(current => current && ({ ...current, photoUrl: null })); setSaved(true);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Could not remove photo."); }
    finally { setBusy(false); }
  };
  if (!draft) return error ? <p role="alert" className="mt-5 text-sm text-red-700">{error}</p> : <LoadingSpinner label="Loading profile…" />;
  return <form onSubmit={save} className="mt-6 space-y-5">
    <div className="flex flex-wrap items-center gap-4">
      <div className="relative grid size-20 shrink-0 place-items-center overflow-hidden rounded-full bg-emerald-800 text-xl font-semibold text-white">
        {profile?.photoUrl ? <Image src={`${profile.photoUrl}?v=${photoVersion}`} alt="Your profile photo" fill sizes="80px" unoptimized className="object-cover" /> : <span aria-hidden="true">{draft.name.split(/\s+/).slice(0, 2).map(part => part[0]).join("").toUpperCase()}</span>}
      </div>
      <div><label className="inline-flex cursor-grab rounded-lg border border-stone-300 px-3 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-50 active:cursor-grabbing">Upload photo<input type="file" accept="image/jpeg,image/png,image/webp" onChange={event => void upload(event)} disabled={busy} className="sr-only" /></label>
        {profile?.photoUrl && <button type="button" onClick={() => void removePhoto()} disabled={busy} className="ml-2 cursor-grab rounded-lg px-3 py-2 text-sm text-stone-600 hover:bg-stone-100 active:cursor-grabbing">Remove</button>}
        <p className="mt-1 text-xs text-stone-500">JPEG, PNG, or WebP · up to 2 MB</p></div>
    </div>
    <label className="block text-sm font-semibold text-stone-800">{draft.role === "therapist" ? "Professional name" : "Display name"}<input required maxLength={200} value={draft.name} onChange={event => update("name", event.target.value)} className={fieldClass} /></label>
    <label className="block text-sm font-semibold text-stone-800">Contact email<input type="email" maxLength={254} value={draft.email ?? ""} onChange={event => update("email", event.target.value)} className={fieldClass} /><span className="mt-1 block text-xs font-normal text-stone-500">Shown to people connected to your care profile. Your sign-in email is managed separately.</span></label>
    <label className="block text-sm font-semibold text-stone-800">Contact phone<input type="tel" maxLength={40} value={draft.phone ?? ""} onChange={event => update("phone", event.target.value)} className={fieldClass} /><span className="mt-1 block text-xs font-normal text-stone-500">Optional; leave blank to hide it from your profile.</span></label>
    {canUseFeature(draft.role, "aboutMe") && <label className="block text-sm font-semibold text-stone-800">About me<textarea maxLength={2000} rows={5} value={draft.aboutMe ?? ""} onChange={event => update("aboutMe", event.target.value)} className={fieldClass} /><span className="mt-1 block text-xs font-normal text-stone-500">A short introduction clients can read on your care profile.</span></label>}
    <div className="flex items-center gap-3 border-t border-stone-200 pt-5"><button disabled={busy} type="submit" className="cursor-grab rounded-lg bg-emerald-800 px-4 py-2 text-sm font-semibold text-white hover:bg-emerald-900 disabled:cursor-wait active:cursor-grabbing">{busy ? "Saving…" : "Save profile"}</button>{saved && <p role="status" className="text-sm font-medium text-emerald-800">Profile saved.</p>}</div>
    {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
  </form>;
}
