export type SummaryItem = {
  label: string
  value: string
}

type ResultSummaryProps = {
  items: SummaryItem[]
}

function ResultSummary({ items }: ResultSummaryProps) {
  return (
    <dl className="tool-summary-grid" aria-label="Tóm tắt kết quả">
      {items.map((item) => (
        <div className="tool-summary-item" key={item.label}>
          <dt className="tool-summary-label">{item.label}</dt>
          <dd className="tool-summary-value" title={item.value}>{item.value}</dd>
        </div>
      ))}
    </dl>
  )
}

export default ResultSummary
