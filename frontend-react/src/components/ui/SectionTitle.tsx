export function SectionTitle({ icon, title }: { icon: string; title: string }) {
  return (
    <div className="mb-3 mt-6 flex items-center gap-2 text-[0.95rem] font-semibold text-text">
      <span className="text-text-muted">{icon}</span>
      <span>{title}</span>
    </div>
  )
}
