from dataclasses import dataclass
from typing import Optional
from ingestion.schema import Severity


@dataclass
class FindingTemplate:
    template_id: str
    title: str
    severity: Severity
    guideline_citation: str
    description_template: str
    reflective_prompt: str
    recommendation: str
    domain: str


FINDING_TEMPLATES = {

    # CPR initiation
    "cpr_delayed": FindingTemplate(
        template_id="cpr_delayed",
        title="CPR initiation delayed",
        severity=Severity.CRITICAL,
        guideline_citation="AHA 2020 Adult Cardiac Arrest Algorithm — Step 1",
        description_template="CPR initiated {delay}s after arrest recognition. AHA recommends initiation within 10 seconds.",
        reflective_prompt="Walk me through the first moments after you recognized the arrest. What happened before compressions started?",
        recommendation="Practice immediate CPR initiation drills — target under 10 seconds from recognition to first compression.",
        domain="cpr_quality"
    ),

    "cpr_pause_excessive": FindingTemplate(
        template_id="cpr_pause_excessive",
        title="CPR pause exceeded limit",
        severity=Severity.CRITICAL,
        guideline_citation="AHA 2020 Adult Cardiac Arrest Algorithm — CCF target >80%",
        description_template="CPR paused for {duration}s at {timestamp}. AHA recommends interruptions under 10 seconds.",
        reflective_prompt="At {timestamp}, compressions stopped for {duration} seconds. What was happening in the room at that moment?",
        recommendation="Drill rhythm checks with a strict 10-second pause limit. Use a timer callout.",
        domain="cpr_quality"
    ),

    "ccf_below_target": FindingTemplate(
        template_id="ccf_below_target",
        title="Chest compression fraction below target",
        severity=Severity.HIGH,
        guideline_citation="AHA 2020 — CCF target >80% throughout resuscitation",
        description_template="Overall chest compression fraction was {ccf}%. AHA target is above 80%.",
        reflective_prompt="Looking at the compression data, the team was doing active compressions only {ccf}% of the time. What do you think contributed to the gaps?",
        recommendation="Focus on minimizing all non-shock pauses. Pre-charge the defibrillator during compressions.",
        domain="cpr_quality"
    ),

    "compression_rate_low": FindingTemplate(
        template_id="compression_rate_low",
        title="Compression rate below target",
        severity=Severity.HIGH,
        guideline_citation="AHA 2020 — Target compression rate 100 to 120 per minute",
        description_template="Average compression rate was {rate} per minute. Target is 100 to 120 per minute.",
        reflective_prompt="The compression rate averaged {rate} per minute. What feedback was the compressor getting during the scenario?",
        recommendation="Use a metronome or feedback device during compressions. Call out rate if it drops.",
        domain="cpr_quality"
    ),

    "compression_rate_high": FindingTemplate(
        template_id="compression_rate_high",
        title="Compression rate above target",
        severity=Severity.MODERATE,
        guideline_citation="AHA 2020 — Target compression rate 100 to 120 per minute",
        description_template="Average compression rate was {rate} per minute. Target is 100 to 120 per minute.",
        reflective_prompt="The compression rate was above the recommended range. How was the team monitoring and adjusting rate?",
        recommendation="Train compressors to self-monitor rate. Use audible feedback devices.",
        domain="cpr_quality"
    ),

    "compression_depth_low": FindingTemplate(
        template_id="compression_depth_low",
        title="Compression depth below target",
        severity=Severity.HIGH,
        guideline_citation="AHA 2020 — Target depth 5 to 6 cm in adults",
        description_template="Average compression depth was {depth}cm. AHA target is 5 to 6cm for adults.",
        reflective_prompt="The compressions averaged {depth}cm in depth. What factors do you think affected the depth during the scenario?",
        recommendation="Practice compression mechanics with feedback device. Emphasize full weight transfer.",
        domain="cpr_quality"
    ),

    # Shock delivery
    "first_shock_delayed": FindingTemplate(
        template_id="first_shock_delayed",
        title="First shock delayed",
        severity=Severity.CRITICAL,
        guideline_citation="AHA 2020 Adult Cardiac Arrest Algorithm — Step 5, shock as soon as available for shockable rhythms",
        description_template="First shock delivered at {timestamp}. For a monitored VF arrest, shock should be delivered as soon as the defibrillator is ready.",
        reflective_prompt="Walk me through the decision process between recognizing VF and delivering the first shock. What caused the delay?",
        recommendation="Pre-position defibrillator before scenario start. Train shock delivery as a parallel task during CPR.",
        domain="shock_delivery"
    ),

    "cpr_not_resumed_post_shock": FindingTemplate(
        template_id="cpr_not_resumed_post_shock",
        title="CPR not immediately resumed after shock",
        severity=Severity.CRITICAL,
        guideline_citation="AHA 2020 — Resume CPR immediately after shock, no pulse check",
        description_template="CPR was not resumed within 10 seconds of shock delivery at {timestamp}. Immediate resumption is required.",
        reflective_prompt="After the shock at {timestamp}, there was a gap before compressions restarted. What was the team doing in those seconds?",
        recommendation="Drill immediate post-shock CPR resumption. No pulse check after shock — resume first, check at next 2-minute mark.",
        domain="shock_delivery"
    ),

    # Drug administration
    "epinephrine_delayed_first": FindingTemplate(
        template_id="epinephrine_delayed_first",
        title="First epinephrine dose delayed",
        severity=Severity.HIGH,
        guideline_citation="AHA 2020 — Epinephrine 1mg IV/IO as soon as feasible for non-shockable rhythms; after second shock for shockable",
        description_template="First epinephrine administered at {timestamp} ({delay}s after recommended window). Target is within 3 to 5 minutes.",
        reflective_prompt="Walk me through your thinking between the second rhythm check and when you ordered epinephrine. What was happening in the room?",
        recommendation="Add epinephrine timing to the team leader's mental checklist. Use time callouts at 3-minute intervals.",
        domain="drug_administration"
    ),

    "epinephrine_interval_exceeded": FindingTemplate(
        template_id="epinephrine_interval_exceeded",
        title="Epinephrine repeat interval exceeded",
        severity=Severity.HIGH,
        guideline_citation="AHA 2020 — Repeat epinephrine every 3 to 5 minutes",
        description_template="Second epinephrine dose given at {timestamp}, {interval}s after first dose. Recommended interval is 3 to 5 minutes.",
        reflective_prompt="The second epinephrine dose came {interval} seconds after the first. How was the team tracking drug timing?",
        recommendation="Designate a recorder role responsible for announcing drug timing reminders at 3-minute intervals.",
        domain="drug_administration"
    ),

    "amiodarone_not_given": FindingTemplate(
        template_id="amiodarone_not_given",
        title="Amiodarone not given after third shock",
        severity=Severity.HIGH,
        guideline_citation="AHA 2020 — Amiodarone 300mg IV/IO after third shock for refractory VF/pVT",
        description_template="Three shocks were delivered but amiodarone was not administered. AHA recommends amiodarone 300mg after the third shock in refractory VF/pVT.",
        reflective_prompt="After the third shock the rhythm remained in VF. What antiarrhythmic options were you considering at that point?",
        recommendation="Add amiodarone after third shock to the team's refractory VF mental model. Include in scenario debrief checklist.",
        domain="drug_administration"
    ),

    "drug_order_incomplete": FindingTemplate(
        template_id="drug_order_incomplete",
        title="Incomplete drug order",
        severity=Severity.MODERATE,
        guideline_citation="TeamSTEPPS — Drug orders should specify drug, dose, and route",
        description_template="Drug order at {timestamp} was incomplete — missing {missing_fields}. Complete orders reduce administration errors.",
        reflective_prompt="At {timestamp} you ordered {drug} without specifying {missing_fields}. How does your team handle incomplete orders in a real code?",
        recommendation="Practice standardized drug order format: drug name, dose, and route in every order. Make it a habit.",
        domain="team_communication"
    ),

    # Rhythm recognition
    "rhythm_check_delayed": FindingTemplate(
        template_id="rhythm_check_delayed",
        title="Rhythm check delayed",
        severity=Severity.HIGH,
        guideline_citation="AHA 2020 — Rhythm check every 2 minutes of CPR",
        description_template="Rhythm check at {timestamp} was {delay}s overdue. Checks should occur every 2 minutes.",
        reflective_prompt="The rhythm check at {timestamp} came later than the recommended 2-minute interval. How was the team tracking CPR cycles?",
        recommendation="Designate a timekeeper. Use verbal 2-minute announcements to trigger rhythm checks.",
        domain="rhythm_recognition"
    ),

    "rhythm_change_callout_missed": FindingTemplate(
        template_id="rhythm_change_callout_missed",
        title="Rhythm change not verbally announced",
        severity=Severity.MODERATE,
        guideline_citation="Closed-loop communication protocol — all significant clinical changes should be verbally announced",
        description_template="Rhythm changed from {from_rhythm} to {to_rhythm} at {timestamp} but no verbal announcement was made within 10 seconds.",
        reflective_prompt="The rhythm changed from {from_rhythm} to {to_rhythm} at {timestamp} but no one called it out. How does your team usually handle rhythm announcements?",
        recommendation="Establish a standard callout protocol for rhythm changes. The person reading the monitor should announce every change.",
        domain="rhythm_recognition"
    ),

    # Communication
    "closed_loop_low": FindingTemplate(
        template_id="closed_loop_low",
        title="Low closed-loop communication rate",
        severity=Severity.MODERATE,
        guideline_citation="TeamSTEPPS — Closed-loop communication expected for all critical orders",
        description_template="Closed-loop confirmation rate was {rate}%. {unconfirmed} of {total} orders were not confirmed back to the team leader.",
        reflective_prompt="Looking at the communication data, {unconfirmed} orders were given without a verbal confirmation back. How does your team know an order was received?",
        recommendation="Practice closed-loop communication in every drill. Make confirmation mandatory for drug orders.",
        domain="team_communication"
    ),

    "repeated_order_detected": FindingTemplate(
        template_id="repeated_order_detected",
        title="Repeated order detected",
        severity=Severity.MODERATE,
        guideline_citation="TeamSTEPPS — Repeated orders signal communication breakdown",
        description_template="Order '{order_text}' was given {count} times, suggesting it was not heard or confirmed the first time.",
        reflective_prompt="The order '{order_text}' was repeated {count} times. What was happening in the room that may have caused the first order to go unheard?",
        recommendation="If an order is not confirmed within 5 seconds, make direct eye contact and repeat by name. Do not assume it was heard.",
        domain="team_communication"
    ),
}


def get_template(template_id: str) -> Optional[FindingTemplate]:
    return FINDING_TEMPLATES.get(template_id)


def format_finding(template_id: str, **kwargs) -> dict:
    template = get_template(template_id)
    if not template:
        raise ValueError(f"Unknown finding template: {template_id}")
    return {
        "template_id": template_id,
        "title": template.title,
        "severity": template.severity.value,
        "guideline_citation": template.guideline_citation,
        "description": template.description_template.format(**kwargs),
        "reflective_prompt": template.reflective_prompt.format(**kwargs),
        "recommendation": template.recommendation,
        "domain": template.domain,
    }
