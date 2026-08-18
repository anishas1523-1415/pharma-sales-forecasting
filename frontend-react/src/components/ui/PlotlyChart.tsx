// Uses the plotly.js "core" build + only the trace types this app actually
// renders (scatter, bar, heatmap, pie) instead of the full plotly.js
// distribution react-plotly.js pulls in by default — that alone was ~4MB
// of the production bundle. Directly relevant to the "no lag" goal: a
// smaller bundle means less JS to parse/execute before the first chart
// paints, especially on a cold Vercel edge load.
import Plotly from 'plotly.js/lib/core'
import scatter from 'plotly.js/lib/scatter'
import bar from 'plotly.js/lib/bar'
import heatmap from 'plotly.js/lib/heatmap'
import pie from 'plotly.js/lib/pie'
import createPlotlyComponent from 'react-plotly.js/factory'
import type { Data, Layout } from 'plotly.js'

Plotly.register([scatter, bar, heatmap, pie])
const Plot = createPlotlyComponent(Plotly)

interface Props {
  data: Data[]
  layout?: Partial<Layout>
  height?: number
}

export function PlotlyChart({ data, layout, height = 420 }: Props) {
  return (
    <Plot
      data={data}
      layout={{ ...layout, height, autosize: true }}
      config={{ responsive: true, displaylogo: false, modeBarButtonsToRemove: ['lasso2d', 'select2d'] }}
      style={{ width: '100%', height: `${height}px` }}
      useResizeHandler
    />
  )
}
