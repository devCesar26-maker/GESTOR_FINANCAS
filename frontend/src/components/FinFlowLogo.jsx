export function FinFlowLogo({ className = '', width = 160, height = 32 }) {
  return (
    <div className={`finflow-logo ${className}`} style={{ display: 'inline-flex', alignItems: 'center', gap: '10px' }}>
      <svg width="28" height="26" viewBox="0 0 28 26" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M2 4L12 13L2 22" stroke="white" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round"/>
        <path d="M12 4L22 13L12 22" stroke="white" strokeWidth="4" strokeLinecap="round" strokeLinejoin="round"/>
        <circle cx="23" cy="13" r="2.5" fill="#60A5FA" />
      </svg>
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
