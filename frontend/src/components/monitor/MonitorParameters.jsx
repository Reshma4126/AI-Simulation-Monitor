import React from "react";
import useMonitorStore from "../../store/monitorStore";

const Block = ({ label, value, unit, color, smallLabel, bigValue, isCrossedOut }) => {
  return (
    <div className="monitor-param-block">
      <div className="monitor-param-label" style={{ color }}>{label}</div>
      {isCrossedOut ? (
        <div className="monitor-param-crossed-out">
          <svg viewBox="0 0 24 24" width="24" height="24" stroke={color} strokeWidth="2" fill="none">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <line x1="3" y1="3" x2="21" y2="21"></line>
            <line x1="21" y1="3" x2="3" y2="21"></line>
          </svg>
        </div>
      ) : (
        <div className="monitor-param-value" style={{ color }}>
          <span className={bigValue ? "param-val-large" : "param-val-normal"}>{value}</span>
          {unit && <span className="param-unit">{unit}</span>}
        </div>
      )}
    </div>
  );
};

const ABPBlock = ({ label, sys, dia, mean, color }) => {
  return (
    <div className="monitor-param-block abp-block">
      <div className="monitor-param-label" style={{ color }}>
        {label}
        <div className="abp-sub-label">Sys.<br/>160<br/>90</div>
      </div>
      <div className="monitor-param-value-container" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
        <div className="monitor-param-value" style={{ color }}>
          <span className="param-val-large" style={{ fontSize: '38px' }}>{sys != null ? Math.round(sys) : "--"}/{dia != null ? Math.round(dia) : "--"}</span>
        </div>
        <div className="param-val-mean" style={{ color, alignSelf: 'center', marginTop: '-4px', fontSize: '20px' }}>({mean != null ? Math.round(mean) : "--"})</div>
      </div>
    </div>
  );
};

const PAPBlock = ({ label, sys, dia, mean, color }) => {
  return (
    <div className="monitor-param-block pap-block">
      <div className="monitor-param-label" style={{ color }}>
        {label}
        <div className="abp-sub-label">Dia.<br/>20<br/>0</div>
      </div>
      <div className="monitor-param-value-container" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
        <div className="monitor-param-value" style={{ color }}>
          <span className="param-val-large" style={{ fontSize: '38px' }}>{sys != null ? Math.round(sys) : "--"}/{dia != null ? Math.round(dia) : "--"}</span>
        </div>
        <div className="param-val-mean" style={{ color, alignSelf: 'center', marginTop: '-4px', fontSize: '20px' }}>({mean != null ? Math.round(mean) : "--"})</div>
      </div>
    </div>
  );
};

export default function MonitorParameters() {
  const state = useMonitorStore();

  const hr = state.HR;
  const spo2 = state.SpO2;
  const abpSys = state.ABP_sys;
  const abpDia = state.ABP_dia;
  const abpMean = state.ABP_mean;
  const papSys = state.PAP_sys;
  const papDia = state.PAP_dia;
  const papMean = state.PAP_mean;
  const etco2 = state.etCO2;
  const rr = state.avRR;

  return (
    <div className="monitor-parameters-container">
      {/* Top Row: HR and Pulse */}
      <div className="monitor-param-row">
        <div className="monitor-param-block hr-block" style={{ width: '50%' }}>
           <div className="monitor-param-label" style={{ color: "#00FF00" }}>HR<br/><span style={{fontSize: '10px'}}>130<br/>50</span></div>
           <div className="monitor-param-value param-val-xl" style={{ color: "#00FF00" }}>{hr ?? "--"}</div>
        </div>
        <div className="monitor-param-block pulse-block" style={{ width: '50%' }}>
           <div className="monitor-param-label" style={{ color: "#FFFF00" }}>Pulse<br/><span style={{fontSize: '10px'}}>130<br/>50</span></div>
           <div className="monitor-param-value param-val-xl" style={{ color: "#FFFF00" }}>{hr ?? "--"}</div>
        </div>
      </div>

      {/* Row 2: SpO2 and Tperi */}
      <div className="monitor-param-row">
        <div className="monitor-param-block" style={{ width: '50%' }}>
           <div className="monitor-param-label" style={{ color: "#FFFF00" }}>SpO2<br/><span style={{fontSize: '10px'}}>100<br/>90</span></div>
           <div className="monitor-param-value param-val-large" style={{ color: "#FFFF00" }}>{spo2 ?? "--"}</div>
        </div>
        <div className="monitor-param-block" style={{ width: '50%', justifyContent: 'flex-end', paddingRight: '20px' }}>
           <Block label="Tperi" color="#00FF00" isCrossedOut={true} />
        </div>
      </div>

      {/* Row 3: ABP and Tblood */}
      <div className="monitor-param-row">
        <div style={{ width: '60%' }}>
          <ABPBlock label="ABP" sys={abpSys} dia={abpDia} mean={abpMean} color="#FF3333" />
        </div>
        <div className="monitor-param-block" style={{ width: '40%', justifyContent: 'flex-end', paddingRight: '10px' }}>
           <Block label="Tblood" color="#00FF00" isCrossedOut={true} />
        </div>
      </div>

      {/* Row 4: PAP and C.O. */}
      <div className="monitor-param-row">
        <div style={{ width: '60%' }}>
           <PAPBlock label="PAP" sys={papSys} dia={papDia} mean={papMean} color="#FF9900" />
        </div>
        <div className="monitor-param-block" style={{ width: '40%', justifyContent: 'flex-end', paddingRight: '10px' }}>
           <div className="monitor-param-block">
             <div className="monitor-param-label" style={{ color: "#FF3333" }}>C.O.</div>
             <div className="monitor-param-value param-val-normal" style={{ color: "#FF3333" }}>--</div>
           </div>
        </div>
      </div>

      {/* Row 5: EtCO2 and awRR */}
      <div className="monitor-param-row">
        <div className="monitor-param-block" style={{ width: '50%' }}>
           <div className="monitor-param-label" style={{ color: "#FFFFFF" }}>etCO2<br/><span style={{fontSize: '10px'}}>65<br/>25</span></div>
           <div className="monitor-param-value param-val-large" style={{ color: "#FFFFFF" }}>{etco2 ?? "--"}</div>
        </div>
        <div className="monitor-param-block" style={{ width: '50%', justifyContent: 'flex-end', paddingRight: '20px' }}>
           <div className="monitor-param-label" style={{ color: "#FFFFFF" }}>awRR<br/><span style={{fontSize: '10px'}}>30<br/>8</span></div>
           <div className="monitor-param-value param-val-large" style={{ color: "#FFFFFF" }}>{rr ?? "--"}</div>
        </div>
      </div>
      
      {/* Spacer */}
      <div style={{ flexGrow: 1 }}></div>

      {/* Bottom Area: NIBP, Gas Placeholders */}
      <div className="monitor-param-bottom-area" style={{ display: 'flex', width: '100%' }}>
        <div className="monitor-param-block" style={{ width: '55%' }}>
          <div className="monitor-param-label" style={{ color: "#FF3333", display: 'flex', flexDirection: 'column' }}>
            <span>NBP Cuff 60<span style={{float: 'right', fontSize: '10px', color: '#ff3333'}}>04:55 PM</span></span>
            <span style={{fontSize: '10px'}}>Sys.</span>
          </div>
          <div className="monitor-param-value-container" style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}>
            <div className="monitor-param-value" style={{ color: "#FF3333" }}>
              <span className="param-val-large" style={{ fontSize: '38px' }}>120/80</span>
            </div>
            <div className="param-val-mean" style={{ color: "#FF3333", alignSelf: 'center', marginTop: '-4px', fontSize: '20px' }}>(93)</div>
          </div>
        </div>
        
        <div className="gas-placeholders" style={{ width: '45%', display: 'flex', flexDirection: 'column', fontSize: '12px', alignItems: 'flex-end', paddingRight: '10px' }}>
          <div style={{color: '#00CCFF', textAlign: 'left', width: '100%', paddingLeft: '5px'}}>imCO2 4</div>
          <div style={{ display: 'flex', gap: '10px', width: '100%', justifyContent: 'space-between', paddingLeft: '5px' }}>
            <Block label="etN2O" color="#00CCFF" isCrossedOut={true} />
            <Block label="etO2" color="#FFFFFF" value="--" />
          </div>
          <div style={{ display: 'flex', gap: '10px', width: '100%', justifyContent: 'space-between', paddingLeft: '5px' }}>
            <Block label="inN2O" color="#00CCFF" isCrossedOut={true} />
            <Block label="inO2" color="#FFFFFF" isCrossedOut={true} />
          </div>
        </div>
      </div>

    </div>
  );
}
