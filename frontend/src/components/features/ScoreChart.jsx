import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export default function ScoreChart({ scans }) {
  const data = (scans || [])
    .filter((s) => s.status === "succeeded" && s.score != null)
    .slice(0, 10)
    .reverse()
    .map((s, i) => ({
      idx: i + 1,
      score: s.score,
      sha: s.head_sha ? s.head_sha.slice(0, 7) : "—",
      date: new Date(s.created_at).toLocaleDateString(),
    }));

  if (data.length < 2) return null;

  return (
    <div className="card" data-testid="score-chart">
      <h2 className="text-sm uppercase tracking-wider text-fg-muted">
        score trend
      </h2>
      <p className="mt-1 text-fg-muted text-xs">
        last {data.length} successful scans
      </p>
      <div className="mt-4 h-40">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart
            data={data}
            margin={{ top: 8, right: 8, bottom: 8, left: 0 }}
          >
            <CartesianGrid stroke="#262626" strokeDasharray="3 3" />
            <XAxis
              dataKey="idx"
              stroke="#525252"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: "#262626" }}
            />
            <YAxis
              stroke="#525252"
              domain={[0, 100]}
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: "#262626" }}
              width={32}
            />
            <Tooltip
              contentStyle={{
                background: "#141414",
                border: "1px solid #3f3f3f",
                borderRadius: 8,
                fontSize: 12,
                color: "#fafafa",
              }}
              labelStyle={{ color: "#a3a3a3" }}
              formatter={(value, _name, ctx) => [
                `${value}/100`,
                ctx.payload.sha,
              ]}
              labelFormatter={(label, payload) =>
                payload && payload[0] ? payload[0].payload.date : `#${label}`
              }
            />
            <Line
              type="monotone"
              dataKey="score"
              stroke="#06b6d4"
              strokeWidth={2}
              dot={{ r: 3, fill: "#06b6d4" }}
              activeDot={{ r: 5 }}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
