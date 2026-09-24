import { ChatIcon } from "@/components/care-relationship-header";

export function CareChat({ partnerName }: { partnerName: string }) {
  return <section aria-label={`Chat with ${partnerName}`} className="flex min-h-[480px] flex-col overflow-hidden rounded-2xl border border-stone-200 bg-white text-left shadow-sm">
    <div className="border-b border-stone-200 px-5 py-4">
      <h2 className="text-lg font-semibold text-stone-900">Chat with {partnerName}</h2>
    </div>
    <div className="flex flex-1 flex-col items-center justify-center gap-3 bg-stone-50 px-6 py-12 text-center">
      <span aria-hidden="true" className="grid size-12 place-items-center rounded-xl border border-stone-200 bg-white text-stone-600"><ChatIcon /></span>
      <p className="max-w-sm text-sm leading-6 text-stone-600">Messaging is coming later. Your conversation will appear here when it’s available.</p>
    </div>
    <div className="flex gap-3 border-t border-stone-200 p-4">
      <input type="text" disabled aria-label="Message" placeholder="Messaging is coming soon" className="min-w-0 flex-1 rounded-xl border border-stone-200 bg-stone-50 px-3 py-2.5 text-sm text-stone-600 disabled:cursor-not-allowed" />
      <button type="button" disabled className="rounded-xl border border-stone-200 bg-stone-100 px-4 py-2.5 text-sm font-semibold text-stone-600 disabled:cursor-not-allowed">Send</button>
    </div>
  </section>;
}
