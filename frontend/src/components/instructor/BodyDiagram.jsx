export default function BodyDiagram() {
  return (
    <div className="body-diagram">
      <svg viewBox="0 0 200 400" className="body-svg">
        {/* Head */}
        <ellipse cx="100" cy="45" rx="28" ry="32" fill="none" stroke="#DAA520" strokeWidth="1.5" />
        {/* Neck */}
        <line x1="100" y1="77" x2="100" y2="95" stroke="#DAA520" strokeWidth="1.5" />
        {/* Body */}
        <rect x="60" y="95" width="80" height="100" rx="5" fill="none" stroke="#DAA520" strokeWidth="1.5" />
        {/* Arms */}
        <line x1="60" y1="105" x2="20" y2="165" stroke="#DAA520" strokeWidth="1.5" />
        <line x1="140" y1="105" x2="180" y2="165" stroke="#DAA520" strokeWidth="1.5" />
        {/* Legs */}
        <line x1="80" y1="195" x2="70" y2="310" stroke="#DAA520" strokeWidth="1.5" />
        <line x1="120" y1="195" x2="130" y2="310" stroke="#DAA520" strokeWidth="1.5" />
        {/* Feet */}
        <line x1="70" y1="310" x2="55" y2="320" stroke="#DAA520" strokeWidth="1.5" />
        <line x1="130" y1="310" x2="145" y2="320" stroke="#DAA520" strokeWidth="1.5" />

        {/* Attachment points */}
        {/* ECG leads */}
        <circle cx="75" cy="115" r="4" fill="#00FF00" opacity="0.8" />
        <text x="55" y="112" fill="#00FF00" fontSize="7" fontFamily="Inter">RA</text>
        <circle cx="125" cy="115" r="4" fill="#00FF00" opacity="0.8" />
        <text x="131" y="112" fill="#00FF00" fontSize="7" fontFamily="Inter">LA</text>
        <circle cx="80" cy="185" r="4" fill="#00FF00" opacity="0.8" />
        <text x="60" y="188" fill="#00FF00" fontSize="7" fontFamily="Inter">RL</text>

        {/* SpO2 probe — finger */}
        <circle cx="18" cy="170" r="4" fill="#FFFF00" opacity="0.8" />
        <text x="2" y="182" fill="#FFFF00" fontSize="7" fontFamily="Inter">SpO₂</text>

        {/* ABP — wrist */}
        <circle cx="180" cy="168" r="4" fill="#FF3333" opacity="0.8" />
        <text x="165" y="180" fill="#FF3333" fontSize="7" fontFamily="Inter">ABP</text>

        {/* Temp — armpit */}
        <circle cx="65" cy="100" r="3" fill="#CC99FF" opacity="0.8" />
        <text x="42" y="98" fill="#CC99FF" fontSize="7" fontFamily="Inter">Temp</text>

        {/* NBP cuff — upper arm */}
        <rect x="145" y="120" width="12" height="25" rx="2" fill="none" stroke="#00CCFF" strokeWidth="1" />
        <text x="159" y="135" fill="#00CCFF" fontSize="7" fontFamily="Inter">NBP</text>
      </svg>
    </div>
  );
}
