import logoUrl from '../assets/logo/LOGO_FINFLOW.svg'

export function FinFlowLogo({ className = '', width = 160, height = 32 }) {
  return (
    <div
      className={`finflow-logo ${className}`}
      style={{ display: 'inline-flex', alignItems: 'center', gap: '10px' }}
    >
      <img
        src={logoUrl}
        alt="FinFlow"
        width="32"
        height="32"
        style={{
          display: 'block',
          width: '32px',
          height: '32px',
          flexShrink: 0,
        }}
      />
      <span style={{
        fontFamily: "'Inter', sans-serif",
        fontWeight: 800,
        fontSize: '1.25rem',
        letterSpacing: '0.04em',
        color: '#FFFFFF',
        textTransform: 'uppercase'
      }}>
        FINFLOW
      </span>
    </div>
  )
}
