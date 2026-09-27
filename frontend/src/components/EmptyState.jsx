export default function EmptyState({ icon: Icon, title, description, action, compact }) {
  return (
    <div className={`flex flex-col items-center justify-center text-center ${compact ? 'py-9 px-5' : 'py-16 px-6'}`}>
      <div className="relative mb-5">
        {/* halo */}
        <span
          className="absolute -inset-3 rounded-full pointer-events-none"
          style={{ background: 'radial-gradient(closest-side, rgba(129,11,56,.35), transparent 72%)' }}
          aria-hidden
        />
        <span
          className="absolute -inset-1.5 rounded-2xl pointer-events-none"
          style={{ border: '1px dashed var(--border-strong)' }}
          aria-hidden
        />
        <div
          className="relative w-12 h-12 rounded-xl flex items-center justify-center border"
          style={{
            background: 'linear-gradient(160deg, rgba(194,20,79,.22), rgba(84,26,26,.28))',
            borderColor: 'rgba(194,20,79,.32)',
            boxShadow: 'inset 0 1px 0 rgba(255,255,255,.08)',
          }}
        >
          {Icon && <Icon size={21} strokeWidth={1.8} className="text-[var(--accent)]" />}
        </div>
      </div>
      <h3 className="text-[15px] font-bold text-[var(--text)] mb-1.5">{title}</h3>
      <p className="text-[13px] text-[var(--text-3)] max-w-sm leading-relaxed mb-5">{description}</p>
      {action}
    </div>
  )
}
