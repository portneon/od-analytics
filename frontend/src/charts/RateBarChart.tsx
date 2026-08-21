import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

interface Props<T> {
  data: T[]
  xKey: keyof T & string
  yKey: keyof T & string
  label: string
  color?: string
  xFormatter?: (value: unknown) => string
}

export function RateBarChart<T extends object>({ data, xKey, yKey, label, color = '#334155', xFormatter }: Props<T>) {
  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
        <XAxis dataKey={xKey as string} tick={{ fontSize: 11, fill: '#94a3b8' }} tickFormatter={xFormatter} />
        <YAxis tick={{ fontSize: 11, fill: '#94a3b8' }} />
        <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8 }} labelFormatter={xFormatter} />
        <Bar dataKey={yKey as string} name={label} fill={color} radius={[3, 3, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  )
}
