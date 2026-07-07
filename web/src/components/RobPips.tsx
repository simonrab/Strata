// Risk-of-bias pip bar. RoB 2 lands in Slice 4, so pips are a placeholder:
// green when a trial is pooled, grey when it's pending human review.
export function RobPips({ pending }: { pending: boolean }) {
  return (
    <div className="flex items-center gap-2">
      <span className="hidden text-[10px] font-semibold uppercase tracking-wider text-ink-muted-light md:inline">
        {pending ? "Pending" : "n/a"}
      </span>
      <div
        className={`flex gap-[2px] rounded-sm border border-hairline-light bg-white p-[2px] ${
          pending ? "opacity-50" : ""
        }`}
        aria-label={pending ? "risk of bias pending" : "risk of bias not yet assessed"}
      >
        {Array.from({ length: 5 }).map((_, i) => (
          <span
            key={i}
            className={`h-3 w-1.5 rounded-[1px] ${pending ? "bg-[#d1d5db]" : "bg-[#d1d5db]"}`}
          />
        ))}
      </div>
    </div>
  );
}
