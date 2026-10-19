import type { PactCard as PactCardType } from "@/lib/mock-data";

const rarityStyles: Record<PactCardType["rarity"], string> = {
  common: "bg-slate-100 text-slate-700",
  rare: "bg-violet-100 text-violet-700",
  epic: "bg-amber-100 text-amber-700",
  legendary: "bg-fuchsia-100 text-fuchsia-700",
};

const statusStyles: Record<PactCardType["status"], string> = {
  active: "bg-emerald-500/10 text-emerald-300",
  completed: "bg-sky-500/10 text-sky-300",
  failed: "bg-rose-500/10 text-rose-300",
};

export function PactCard({ pact }: { pact: PactCardType }) {
  return (
    <article className="rounded-3xl border border-white/10 bg-white/5 p-5 shadow-[0_20px_60px_rgba(24,17,46,0.35)] backdrop-blur-sm">
      <div className="mb-4 flex items-center justify-between gap-3">
        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${rarityStyles[pact.rarity]}`}>
          {pact.rarity}
        </span>
        <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${statusStyles[pact.status]}`}>
          {pact.status}
        </span>
      </div>

      <h3 className="text-xl font-semibold text-white">{pact.title}</h3>
      <p className="mt-2 text-sm leading-6 text-slate-300">{pact.description}</p>

      <div className="mt-5 flex items-center justify-between text-xs text-slate-400">
        <span>{pact.creator}</span>
        <span>{pact.type}</span>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-3 text-sm text-slate-300">
        <div>
          <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Срок</div>
          <div className="mt-1 font-medium">{pact.deadline}</div>
        </div>
        <div>
          <div className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Условие</div>
          <div className="mt-1 font-medium">{pact.stake}</div>
        </div>
      </div>

      <button className="mt-5 w-full rounded-full border border-white/15 bg-white/5 px-4 py-2 text-sm font-medium text-white transition hover:border-white/30 hover:bg-white/10">
        Активировать
      </button>
    </article>
  );
}
