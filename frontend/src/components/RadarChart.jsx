import { Radar, RadarChart as RC, PolarGrid, PolarAngleAxis, ResponsiveContainer, Tooltip } from 'recharts'

export default function RadarChart({ data, height = 260, color = '#c2144f' }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <RC data={data} outerRadius="72%">
        <defs>
          <radialGradient id="radarFill" cx="50%" cy="50%" r="65%">
            <stop offset="0%" stopColor={color} stopOpacity={0.62} />
            <stop offset="100%" stopColor={color} stopOpacity={0.12} />
          </radialGradient>
        </defs>
        <PolarGrid stroke="var(--border)" radialLines />
        <PolarAngleAxis
          dataKey="subject"
          tick={{ fill: 'var(--text-2)', fontSize: 11.5, fontWeight: 600 }}
        />
        <Radar
          dataKey="score"
          stroke={color}
          fill="url(#radarFill)"
          strokeWidth={2}
          dot={{ r: 3, fill: color, strokeWidth: 0 }}
          isAnimationActive
          animationDuration={900}
        />
        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null
            const row = payload[0].payload
            return (
              <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] shadow-md px-3 py-2 text-[12.5px]">
                <p className="font-semibold text-[var(--text)]">{row.subject}</p>
                <p className="text-[var(--text-2)]">{Math.round(row.score)} / 100</p>
              </div>
            )
          }}
        />
      </RC>
    </ResponsiveContainer>
  )
}
