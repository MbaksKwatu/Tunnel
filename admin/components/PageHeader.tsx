interface PageHeaderProps {
  title: string
  subtitle?: string
}

export function PageHeader({ title, subtitle }: PageHeaderProps) {
  return (
    <div style={{ marginBottom: 32 }}>
      <h1 style={{
        fontFamily: "'IBM Plex Serif', serif",
        fontWeight: 400,
        fontSize: 26,
        color: 'var(--navy)',
        lineHeight: 1.2,
      }}>
        {title}
      </h1>
      {subtitle && (
        <p style={{
          marginTop: 6,
          fontFamily: "'IBM Plex Sans', sans-serif",
          fontSize: 14,
          color: 'var(--t1)',
          fontWeight: 400,
        }}>
          {subtitle}
        </p>
      )}
    </div>
  )
}
