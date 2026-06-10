"""UAV flight-control cross-domain dataset (SW HLR ↔ HW/FPGA HWR).

Purpose
-------
Phase 2 of the evidence-hardening plan. The dissertation's *unique niche* is
cross-domain SW↔FPGA binding, but the three ``CROSS-*`` compliance objectives
(:mod:`specguard.compliance.cross_domain`) previously ran only against the
hand-authored synthetic seed in ``scripts/load_neo4j.py``. This module replaces
that invented metadata with a **derived, citable** case study:

* a single UAV flight-control function whose **hardware side is the CVA6 core**
  (the FPGA-hosted processor that runs the flight-control software), so the
  existing CVA6 requirements dataset becomes the HWR anchor of one case study;
* a **software side derived from public UAV autopilot documentation** (PX4 and
  ArduPilot), so the timing budgets, loop cadences and failsafe behaviour are
  grounded in real, published engineering figures rather than invented numbers.

HONESTY (per CLAUDE.md)
-----------------------
This is a **derived, illustrative dataset authored for this study** to
demonstrate that the cross-domain objectives are *executable and
discriminating* on realistic data. It is **NOT** a requirements baseline from a
real certified UAV program, and it is **NOT** certification evidence. No public
UAV autopilot ships a DO-178C/DO-254 requirement set with DAL assignments,
HLR/HWR decomposition and traceability; that material does not exist publicly.

Provenance is separated explicitly throughout:

* "derived from PX4/ArduPilot docs" — the *engineering facts* (loop rates,
  cadences, failsafe semantics) are taken from the cited public documentation
  and reproduced in the ``provenance`` field of each requirement;
* "authored for this study" — the *requirement wording* ("shall ..."), the
  HLR/HWR decomposition, the timing-budget arithmetic, the DAL assignments and
  the mini-FHA are our own construction, marked as such.

Sources (accessed 2026-06-10)
-----------------------------
PX4 (BSD-3-Clause project documentation):
* PX4 architecture / controller concept — IMU sampled at 1 kHz, integrated and
  published at 250 Hz; cascaded position → attitude → rate controllers.
  https://docs.px4.io/main/en/concept/architecture.html
* PX4 control-loop cadence discussion — attitude/rate inner loop ~250 Hz,
  position outer loop ~100 Hz (synchronised to the state estimator).
  https://discuss.px4.io/t/control-loop-update-frequency/14043

ArduPilot (GPLv3 project documentation):
* Aggressive rate-loop tuning — main loop runs at 400 Hz (2.5 ms period);
  fast-rate thread can run attitude rate PIDs up to 4 kHz gyro rate
  (2.5 µs corrections).
  https://ardupilot.org/copter/docs/high-loop-rate-tuning.html
* ArduCopter failsafe documentation — radio/GCS link-loss, battery and EKF
  failsafes trigger a bounded, deterministic safe-state transition.
  https://ardupilot.org/copter/docs/failsafe-landing-page.html

CVA6 (the HW/FPGA anchor) — see :mod:`specguard.data.cva6_requirements`:
Official CVA6 Requirements Specification v1.0.1 (OpenHW Group / Thales).
HWR requirements below reference real CVA6 capability IDs (IRQ-10 interrupt
handling, MEM-10 AXI5 memory interface, L1W-10 write-through cache timing,
FET-10 FENCE.T timing isolation, ISA-60 FPU) so the two datasets bind into one
case study.

Design decisions & trade-offs
-----------------------------
*Timing budgets.* System-level budgets are expressed in nanoseconds (the unit
the ``CROSS-TIMING-1`` Cypher sums) and derived from published loop periods:
250 Hz → 4,000,000 ns, 100 Hz → 10,000,000 ns, 1 kHz → 1,000,000 ns, 400 Hz →
2,500,000 ns. Each system budget is split into a SW (HLR) computation share and
a HW (HWR) latency share whose realistic sum sits *below* the period (control
loops cannot consume their entire period). The split percentages are our
engineering judgement, documented per requirement; only their *arithmetic*
relationship to the system budget is load-bearing for the objective.

*Mini-FHA.* The three hazards use ARP4761 severity vocabulary
(catastrophic / hazardous / major). We keep the FHA deliberately small (3
hazards) and assign severities to exercise the objective's
catastrophic/hazardous gate: a catastrophic loss-of-attitude-control hazard and
a hazardous motor-runaway hazard both require dual-domain mitigation; a *major*
sensor-glitch hazard does not (below the objective's severity threshold), which
documents why single-domain mitigation is acceptable there.

*Deliberate seeding.* To prove the objectives *discriminate* (fire on faults,
pass on clean pairs) rather than merely fire, each objective has at least one
seeded violation **and** a compliant counterpart. The full registry is
:data:`SEEDED_VIOLATIONS`; tests assert each seeded condition is genuinely
present in the data (e.g. the budget arithmetic really overruns).

Schema contract (consumed by the loader and the CROSS-* Cypher)
---------------------------------------------------------------
* ``SystemRequirement`` → Neo4j ``:Requirement {level:'system', timing_budget_ns}``
* ``DomainRequirement`` (level ``'HLR'`` or ``'HWR'``) →
  ``:Requirement {level, timing_budget_ns?}`` with ``DERIVES_FROM`` → system.
* ``Interface`` → ``:Interface``; SW & HW reqs ``MENTIONS`` it; a
  ``consistent`` flag controls the ``CONSISTENT_WITH`` SW→HW edge.
* ``Hazard`` → ``:SafetyHazard {severity, mitigation_domain}`` with
  ``MITIGATES`` edges from the listed SW/HW requirement IDs.

This module is **stdlib-only** (dataclasses + typing) so it stays importable
from the DO-330-qualifiable core path.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SystemRequirement:
    """A system-level (ARP4754A allocation) requirement with a timing budget.

    ``timing_budget_ns`` is the end-to-end period the SW+HW children must fit
    within; the ``CROSS-TIMING-1`` objective sums the children's budgets and
    flags an overrun.
    """

    req_id: str
    text: str
    timing_budget_ns: int
    dal: str
    provenance: str
    """Where the engineering figure came from (cited) vs. authored for study."""


@dataclass(frozen=True)
class DomainRequirement:
    """A software (HLR / DO-178C) or hardware (HWR / DO-254) child requirement.

    ``level`` is ``'HLR'`` (software) or ``'HWR'`` (hardware/FPGA). ``cva6_ref``
    points at the real CVA6 requirement ID the HWR is anchored in (None for SW).
    """

    req_id: str
    text: str
    level: str  # 'HLR' | 'HWR'
    dal: str
    derives_from: str  # parent SystemRequirement.req_id
    timing_budget_ns: int | None
    provenance: str
    cva6_ref: str | None = None
    is_derived: bool = False


@dataclass(frozen=True)
class Interface:
    """A shared HW/SW interface both domains reference (MENTIONS).

    ``consistent`` controls whether a ``CONSISTENT_WITH`` edge is asserted
    between the SW HLR and HW HWR that both mention it. ``False`` seeds a
    ``CROSS-HW-SW-1`` violation.
    """

    name: str
    description: str
    sw_req: str
    hw_req: str
    consistent: bool
    provenance: str


@dataclass(frozen=True)
class Hazard:
    """A mini-FHA hazard with ARP4761 severity and required mitigation domain.

    ``severity`` ∈ {catastrophic, hazardous, major, minor}. ``mitigation_domain``
    ∈ {both, sw_and_hw, sw, hw}. The ``CROSS-SAFETY-1`` objective requires that
    catastrophic/hazardous hazards needing dual-domain mitigation have BOTH an
    HLR and an HWR ``MITIGATES`` edge.
    """

    haz_id: str
    description: str
    severity: str
    mitigation_domain: str
    sw_mitigators: list[str] = field(default_factory=list)
    hw_mitigators: list[str] = field(default_factory=list)
    provenance: str = ""


# ===========================================================================
# System-level requirements (ARP4754A allocation — authored for this study;
# timing budgets DERIVED from cited PX4/ArduPilot loop periods).
# ===========================================================================
#
# Period → ns conversions (load-bearing for CROSS-TIMING-1):
#   250 Hz  -> 4_000_000 ns   (PX4 attitude/rate inner loop)
#   100 Hz  -> 10_000_000 ns  (PX4 position outer loop)
#   1 kHz   -> 1_000_000 ns   (PX4 IMU sample/publish cadence)
#   400 Hz  -> 2_500_000 ns   (ArduPilot main loop period)

SYSTEM_REQUIREMENTS: list[SystemRequirement] = [
    SystemRequirement(
        req_id="UAV-SYS-10",
        text=(
            "The flight-control function shall complete one attitude rate "
            "control iteration within 4 ms, sustaining a 250 Hz inner-loop "
            "rate under worst-case execution conditions."
        ),
        timing_budget_ns=4_000_000,
        dal="A",
        provenance=(
            "DERIVED from PX4: the attitude controller publishes desired "
            "angular rates and the rate controller runs at ~250 Hz (4 ms "
            "period). Budget value and 'shall' wording AUTHORED for this study. "
            "Source: docs.px4.io/main/en/concept/architecture.html; "
            "discuss.px4.io/t/control-loop-update-frequency/14043"
        ),
    ),
    SystemRequirement(
        req_id="UAV-SYS-20",
        text=(
            "The flight-control function shall complete one position control "
            "iteration within 10 ms, sustaining a 100 Hz outer-loop rate "
            "synchronised to the state estimator."
        ),
        timing_budget_ns=10_000_000,
        dal="A",
        provenance=(
            "DERIVED from PX4: the position control outer loop runs at 100 Hz "
            "(10 ms), synchronised to the EKF state estimate. Budget value and "
            "wording AUTHORED for this study. "
            "Source: discuss.px4.io/t/control-loop-update-frequency/14043"
        ),
    ),
    SystemRequirement(
        req_id="UAV-SYS-30",
        text=(
            "The flight-control function shall acquire and integrate one IMU "
            "sample within 1 ms, sustaining a 1 kHz sensor acquisition rate."
        ),
        timing_budget_ns=1_000_000,
        dal="A",
        provenance=(
            "DERIVED from PX4: IMU drivers sample at 1 kHz, integrate and "
            "publish at 250 Hz. Acquisition budget (1 ms) and wording AUTHORED "
            "for this study. "
            "Source: docs.px4.io/main/en/concept/architecture.html"
        ),
    ),
    SystemRequirement(
        req_id="UAV-SYS-40",
        text=(
            "The flight-control function shall detect loss of the radio "
            "control link and enter the configured failsafe mode within 2 ms."
        ),
        # NOTE: 2_000_000 ns is DELIBERATELY too small for its children
        #       (see SEEDED_VIOLATIONS: TIMING_OVERRUN). A realistic failsafe
        #       reaction is far slower, but we tighten the *system* budget here
        #       so the child allocations provably overrun it.
        timing_budget_ns=2_000_000,
        dal="A",
        provenance=(
            "DERIVED from ArduPilot: radio/GCS link-loss failsafes trigger a "
            "bounded deterministic safe-state transition. The specific 2 ms "
            "system budget is AUTHORED for this study and DELIBERATELY tight to "
            "seed a cross-domain budget overrun (see SEEDED_VIOLATIONS). "
            "Source: ardupilot.org/copter/docs/failsafe-landing-page.html"
        ),
    ),
    SystemRequirement(
        req_id="UAV-SYS-50",
        text=(
            "The flight-control function shall update the motor output "
            "commands within 2.5 ms, sustaining a 400 Hz actuator command "
            "rate."
        ),
        timing_budget_ns=2_500_000,
        dal="A",
        provenance=(
            "DERIVED from ArduPilot: the main loop runs at 400 Hz (2.5 ms "
            "period), driving the attitude rate PID and motor mixer. Budget "
            "value and wording AUTHORED for this study. "
            "Source: ardupilot.org/copter/docs/high-loop-rate-tuning.html"
        ),
    ),
    SystemRequirement(
        req_id="UAV-SYS-60",
        text=(
            "The flight-control function shall detect a control-task overrun "
            "via a hardware watchdog and command the configured failsafe mode "
            "within 5 ms."
        ),
        timing_budget_ns=5_000_000,
        dal="A",
        provenance=(
            "DERIVED from ArduPilot/PX4 watchdog-based task-overrun detection. "
            "5 ms detection budget and wording AUTHORED for this study. "
            "Source: ardupilot.org/copter/docs/failsafe-landing-page.html"
        ),
    ),
]


# ===========================================================================
# Domain requirements: SW (HLR / DO-178C) + HW (HWR / DO-254, CVA6-anchored).
# ===========================================================================
#
# Timing-budget split rationale (authored; only arithmetic vs. parent matters):
#   A control iteration spends part of the period in software computation
#   (HLR latency share) and part in hardware service latency (HWR share).
#   The realistic shares sit well below the parent period for the COMPLIANT
#   loops; UAV-SYS-40's children intentionally exceed its 2 ms budget.

DOMAIN_REQUIREMENTS: list[DomainRequirement] = [
    # --- UAV-SYS-10 (attitude rate, 4 ms) — COMPLIANT pair: 1.5 + 1.0 = 2.5 ms
    DomainRequirement(
        req_id="UAV-HLR-10",
        text=(
            "The rate controller software shall compute the three-axis angular "
            "rate PID correction and write the mixer setpoints within 1.5 ms "
            "of receiving a gyro sample."
        ),
        level="HLR",
        dal="A",
        derives_from="UAV-SYS-10",
        timing_budget_ns=1_500_000,
        provenance=(
            "DERIVED from PX4 cascaded rate controller (angular-rate PID). "
            "1.5 ms SW computation share AUTHORED for this study. "
            "Source: docs.px4.io/main/en/concept/architecture.html"
        ),
    ),
    DomainRequirement(
        req_id="UAV-HWR-10",
        text=(
            "The CVA6 core shall service a gyro interrupt and deliver the "
            "sample to the rate controller task within 1.0 ms of assertion."
        ),
        level="HWR",
        dal="A",
        derives_from="UAV-SYS-10",
        timing_budget_ns=1_000_000,
        cva6_ref="IRQ-10",
        provenance=(
            "HW side anchored in CVA6 IRQ-10 (interrupt handling registers + "
            "CLINT interface). 1.0 ms interrupt-to-task latency share AUTHORED "
            "for this study. Source: CVA6 Requirements Specification v1.0.1."
        ),
    ),
    # --- UAV-SYS-20 (position, 10 ms) — COMPLIANT pair: 4 + 3 = 7 ms
    DomainRequirement(
        req_id="UAV-HLR-20",
        text=(
            "The position controller software shall compute the desired "
            "attitude setpoint from the navigation state estimate within 4 ms."
        ),
        level="HLR",
        dal="A",
        derives_from="UAV-SYS-20",
        timing_budget_ns=4_000_000,
        provenance=(
            "DERIVED from PX4 position controller (outer loop on EKF state). "
            "4 ms SW share AUTHORED for this study. "
            "Source: discuss.px4.io/t/control-loop-update-frequency/14043"
        ),
    ),
    DomainRequirement(
        req_id="UAV-HWR-20",
        text=(
            "The CVA6 core shall complete the navigation state load from the "
            "AXI5 memory interface within 3 ms, including cache-miss handling."
        ),
        level="HWR",
        dal="A",
        derives_from="UAV-SYS-20",
        timing_budget_ns=3_000_000,
        cva6_ref="MEM-10",
        provenance=(
            "HW side anchored in CVA6 MEM-10 (AXI5 memory interface) and "
            "L1W-10 (write-through cache timing). 3 ms memory-access share "
            "AUTHORED for this study. Source: CVA6 Requirements Spec v1.0.1."
        ),
    ),
    # --- UAV-SYS-30 (IMU acquisition, 1 ms) — COMPLIANT pair: 0.3 + 0.5 = 0.8 ms
    DomainRequirement(
        req_id="UAV-HLR-30",
        text=(
            "The sensor acquisition software shall integrate one IMU sample "
            "into the rate estimate within 300 us of sample arrival."
        ),
        level="HLR",
        dal="A",
        derives_from="UAV-SYS-30",
        timing_budget_ns=300_000,
        provenance=(
            "DERIVED from PX4 IMU integrate-and-publish pipeline. 300 us SW "
            "integration share AUTHORED for this study. "
            "Source: docs.px4.io/main/en/concept/architecture.html"
        ),
    ),
    DomainRequirement(
        req_id="UAV-HWR-30",
        text=(
            "The CVA6 core shall transfer one IMU sample block from the sensor "
            "DMA channel to coherent memory within 500 us of channel ready."
        ),
        level="HWR",
        dal="A",
        derives_from="UAV-SYS-30",
        timing_budget_ns=500_000,
        cva6_ref="MEM-20",
        provenance=(
            "HW side anchored in CVA6 MEM-20 (AXI user-bit extensions used for "
            "DMA datasize) and L1W-10 cache coherence. 500 us DMA-transfer "
            "share AUTHORED for this study. Source: CVA6 Requirements Spec."
        ),
    ),
    # --- UAV-SYS-40 (failsafe, 2 ms budget) — VIOLATION pair: 1.5 + 1.0 = 2.5 ms
    DomainRequirement(
        req_id="UAV-HLR-40",
        text=(
            "The failsafe monitor software shall detect a stale radio control "
            "frame and command the configured failsafe mode within 1.5 ms."
        ),
        level="HLR",
        dal="A",
        derives_from="UAV-SYS-40",
        timing_budget_ns=1_500_000,
        provenance=(
            "DERIVED from ArduPilot radio failsafe (stale-frame detection -> "
            "failsafe action). 1.5 ms SW detection share AUTHORED for this "
            "study; combined with HWR-40 it DELIBERATELY overruns the 2 ms "
            "system budget (SEEDED_VIOLATIONS: TIMING_OVERRUN). "
            "Source: ardupilot.org/copter/docs/failsafe-landing-page.html"
        ),
    ),
    DomainRequirement(
        req_id="UAV-HWR-40",
        text=(
            "The CVA6 core shall flush in-flight cache state on the FENCE.T "
            "boundary and present a deterministic timing window within 1.0 ms "
            "during the failsafe transition."
        ),
        level="HWR",
        dal="A",
        derives_from="UAV-SYS-40",
        timing_budget_ns=1_000_000,
        cva6_ref="FET-10",
        provenance=(
            "HW side anchored in CVA6 FET-10 (FENCE.T timing-isolation custom "
            "instruction). 1.0 ms deterministic-window share AUTHORED for this "
            "study; 1.5 + 1.0 = 2.5 ms > 2 ms budget (DELIBERATE overrun). "
            "Source: CVA6 Requirements Specification v1.0.1."
        ),
    ),
    # --- UAV-SYS-50 (motor output, 2.5 ms) — COMPLIANT pair: 1.0 + 0.8 = 1.8 ms
    DomainRequirement(
        req_id="UAV-HLR-50",
        text=(
            "The motor mixer software shall convert the rate controller output "
            "into per-motor PWM duty values within 1.0 ms."
        ),
        level="HLR",
        dal="A",
        derives_from="UAV-SYS-50",
        timing_budget_ns=1_000_000,
        provenance=(
            "DERIVED from ArduPilot motor mixer in the 400 Hz main loop. 1.0 ms "
            "SW mixing share AUTHORED for this study. "
            "Source: ardupilot.org/copter/docs/high-loop-rate-tuning.html"
        ),
    ),
    DomainRequirement(
        req_id="UAV-HWR-50",
        text=(
            "The CVA6 core shall write the per-motor PWM duty values to the "
            "memory-mapped actuator register block within 800 us."
        ),
        level="HWR",
        dal="A",
        derives_from="UAV-SYS-50",
        timing_budget_ns=800_000,
        cva6_ref="MEM-10",
        provenance=(
            "HW side anchored in CVA6 MEM-10 (AXI5 memory-mapped register "
            "writes). 800 us register-write share AUTHORED for this study. "
            "Source: CVA6 Requirements Specification v1.0.1."
        ),
    ),
    # --- UAV-SYS-60 (watchdog overrun, 5 ms) — COMPLIANT pair: 1.0 + 1.5 = 2.5 ms
    DomainRequirement(
        req_id="UAV-HLR-70",
        text=(
            "The health monitor software shall service the watchdog within "
            "1.0 ms of each control-task completion and withhold servicing on "
            "a detected overrun."
        ),
        level="HLR",
        dal="A",
        derives_from="UAV-SYS-60",
        timing_budget_ns=1_000_000,
        provenance=(
            "DERIVED from ArduPilot/PX4 watchdog servicing. 1.0 ms servicing "
            "share AUTHORED for this study. "
            "Source: ardupilot.org/copter/docs/failsafe-landing-page.html"
        ),
    ),
    DomainRequirement(
        req_id="UAV-HWR-70",
        text=(
            "The CVA6 core shall raise a non-maskable watchdog interrupt and "
            "drive the failsafe output line within 1.5 ms of watchdog expiry."
        ),
        level="HWR",
        dal="A",
        derives_from="UAV-SYS-60",
        timing_budget_ns=1_500_000,
        cva6_ref="IRQ-10",
        provenance=(
            "HW side anchored in CVA6 IRQ-10 (interrupt handling). 1.5 ms "
            "watchdog-to-safe-state share AUTHORED for this study. "
            "Source: CVA6 Requirements Specification v1.0.1."
        ),
    ),
    # --- Extra SW/HW pair anchoring the FPU interface (no own timing budget) ---
    DomainRequirement(
        req_id="UAV-HLR-60",
        text=(
            "The attitude estimator software shall compute the quaternion "
            "update using single-precision floating-point arithmetic."
        ),
        level="HLR",
        dal="A",
        derives_from="UAV-SYS-10",
        timing_budget_ns=None,
        provenance=(
            "DERIVED from PX4 attitude estimator (floating-point quaternion "
            "maths). Wording AUTHORED for this study."
        ),
    ),
    DomainRequirement(
        req_id="UAV-HWR-60",
        text=(
            "The CVA6 core shall execute single-precision floating-point "
            "operations in hardware via the F extension."
        ),
        level="HWR",
        dal="A",
        derives_from="UAV-SYS-10",
        timing_budget_ns=None,
        cva6_ref="ISA-60",
        provenance=(
            "HW side anchored in CVA6 ISA-60 (F/D floating-point extensions). "
            "Wording AUTHORED for this study. Source: CVA6 Requirements Spec."
        ),
    ),
]


# ===========================================================================
# Shared HW/SW interfaces (MENTIONS from both sides; CONSISTENT_WITH = clean).
# ===========================================================================

INTERFACES: list[Interface] = [
    # COMPLIANT: gyro interrupt line, consistency asserted.
    Interface(
        name="GYRO_IRQ_LINE",
        description="Gyro data-ready interrupt line into the CVA6 CLINT.",
        sw_req="UAV-HLR-10",
        hw_req="UAV-HWR-10",
        consistent=True,
        provenance=(
            "Interface concept DERIVED from PX4 gyro-driven rate loop + CVA6 "
            "IRQ-10/CLINT. AUTHORED for this study."
        ),
    ),
    # COMPLIANT: memory-mapped actuator register block, consistency asserted.
    Interface(
        name="ACTUATOR_MMAP_REGS",
        description="Memory-mapped PWM actuator register block on the AXI bus.",
        sw_req="UAV-HLR-50",
        hw_req="UAV-HWR-50",
        consistent=True,
        provenance=(
            "Interface concept DERIVED from ArduPilot motor output + CVA6 "
            "MEM-10 AXI5 register writes. AUTHORED for this study."
        ),
    ),
    # COMPLIANT: sensor DMA channel, consistency asserted.
    Interface(
        name="IMU_DMA_CHANNEL",
        description="DMA channel transferring IMU sample blocks to memory.",
        sw_req="UAV-HLR-30",
        hw_req="UAV-HWR-30",
        consistent=True,
        provenance=(
            "Interface concept DERIVED from PX4 IMU pipeline + CVA6 MEM-20 "
            "AXI user-bit datasize extensions. AUTHORED for this study."
        ),
    ),
    # VIOLATION (SEEDED): FPU control/status interface mentioned by both
    # sides but NO CONSISTENT_WITH edge — seeds CROSS-HW-SW-1.
    Interface(
        name="FPU_CSR_BLOCK",
        description="Floating-point control/status register block (fcsr).",
        sw_req="UAV-HLR-60",
        hw_req="UAV-HWR-60",
        consistent=False,
        provenance=(
            "Interface concept DERIVED from CVA6 ISA-60 FPU (fcsr) + PX4 "
            "attitude estimator. AUTHORED for this study. Consistency "
            "DELIBERATELY left unasserted (SEEDED_VIOLATIONS: MISSING_CONSISTENCY)."
        ),
    ),
]


# ===========================================================================
# Mini-FHA hazards (ARP4761 severity vocabulary).
# ===========================================================================

HAZARDS: list[Hazard] = [
    # COMPLIANT: catastrophic hazard with BOTH SW and HW mitigation.
    Hazard(
        haz_id="UAV-HAZ-1",
        description=(
            "Loss of attitude control due to missed rate-control deadline "
            "leading to uncommanded divergence."
        ),
        severity="catastrophic",
        mitigation_domain="both",
        sw_mitigators=["UAV-HLR-10"],
        hw_mitigators=["UAV-HWR-10"],
        provenance=(
            "Hazard and severity (catastrophic) AUTHORED for this study, "
            "informed by the safety-criticality of the PX4 250 Hz rate loop. "
            "Dual-domain mitigation present (compliant)."
        ),
    ),
    # VIOLATION (SEEDED): hazardous hazard, dual-domain required, HW side only.
    Hazard(
        haz_id="UAV-HAZ-2",
        description=(
            "Motor runaway: actuator command path emits a saturated PWM value "
            "after a stale rate setpoint."
        ),
        severity="hazardous",
        mitigation_domain="both",
        sw_mitigators=[],  # DELIBERATELY missing SW-side mitigation
        hw_mitigators=["UAV-HWR-50"],
        provenance=(
            "Hazard and severity (hazardous) AUTHORED for this study, informed "
            "by ArduPilot motor-output failsafe behaviour. SW mitigation "
            "DELIBERATELY omitted (SEEDED_VIOLATIONS: SINGLE_DOMAIN_HAZARD); "
            "only HW-side (UAV-HWR-50) mitigates."
        ),
    ),
    # COMPLIANT (control case): major hazard, below the dual-domain severity
    # threshold, so single-domain (SW) mitigation is acceptable and the
    # objective must NOT fire on it.
    Hazard(
        haz_id="UAV-HAZ-3",
        description=(
            "Transient IMU sample glitch causing a single-frame estimate "
            "error, recovered by the next sample."
        ),
        severity="major",
        mitigation_domain="sw",
        sw_mitigators=["UAV-HLR-30"],
        hw_mitigators=[],
        provenance=(
            "Hazard and severity (major) AUTHORED for this study. Below the "
            "catastrophic/hazardous threshold, so single-domain (SW) "
            "mitigation is acceptable; the objective must NOT fire here."
        ),
    ),
]


# ===========================================================================
# Seeded-violation registry — the contract tests assert against.
# ===========================================================================


@dataclass(frozen=True)
class SeededViolation:
    """A deliberately injected cross-domain defect and its compliant twin."""

    key: str
    objective_id: str
    description: str
    violating_element: str
    """The element the objective is expected to flag."""
    compliant_counterpart: str
    """A structurally similar element that must NOT be flagged."""
    why: str


SEEDED_VIOLATIONS: list[SeededViolation] = [
    SeededViolation(
        key="TIMING_OVERRUN",
        objective_id="CROSS-TIMING-1",
        description=(
            "UAV-SYS-40 (failsafe) has a 2,000,000 ns budget but its children "
            "UAV-HLR-40 (1,500,000) + UAV-HWR-40 (1,000,000) sum to "
            "2,500,000 ns — a 500,000 ns overrun."
        ),
        violating_element="UAV-SYS-40",
        compliant_counterpart="UAV-SYS-10",  # 1.5+1.0=2.5 ms < 4 ms
        why=(
            "Single-domain tools see each child fitting its own share; only a "
            "cross-domain sum detects the system-budget overrun."
        ),
    ),
    SeededViolation(
        key="MISSING_CONSISTENCY",
        objective_id="CROSS-HW-SW-1",
        description=(
            "UAV-HLR-60 and UAV-HWR-60 both MENTIONS the FPU_CSR_BLOCK "
            "interface, but no CONSISTENT_WITH edge is asserted between them."
        ),
        violating_element="FPU_CSR_BLOCK",
        compliant_counterpart="GYRO_IRQ_LINE",  # has CONSISTENT_WITH
        why=(
            "Mismatched HW/SW interface specs are a classic integration defect "
            "that slips through single-domain verification."
        ),
    ),
    SeededViolation(
        key="SINGLE_DOMAIN_HAZARD",
        objective_id="CROSS-SAFETY-1",
        description=(
            "UAV-HAZ-2 (hazardous, dual-domain required) is mitigated only on "
            "the HW side (UAV-HWR-50); no HLR MITIGATES edge exists."
        ),
        violating_element="UAV-HAZ-2",
        compliant_counterpart="UAV-HAZ-1",  # dual-domain mitigation present
        why=(
            "Catastrophic/hazardous hazards needing defence-in-depth require "
            "mitigation on BOTH sides; single-domain coverage is insufficient."
        ),
    ),
]


# ===========================================================================
# Accessors
# ===========================================================================


def get_system_requirements() -> list[SystemRequirement]:
    """Return the system-level requirements."""
    return SYSTEM_REQUIREMENTS


def get_domain_requirements() -> list[DomainRequirement]:
    """Return all HLR + HWR domain requirements."""
    return DOMAIN_REQUIREMENTS


def get_hlr_requirements() -> list[DomainRequirement]:
    """Return only software (HLR / DO-178C) requirements."""
    return [r for r in DOMAIN_REQUIREMENTS if r.level == "HLR"]


def get_hwr_requirements() -> list[DomainRequirement]:
    """Return only hardware (HWR / DO-254, CVA6-anchored) requirements."""
    return [r for r in DOMAIN_REQUIREMENTS if r.level == "HWR"]


def get_interfaces() -> list[Interface]:
    """Return the shared HW/SW interfaces."""
    return INTERFACES


def get_hazards() -> list[Hazard]:
    """Return the mini-FHA hazards."""
    return HAZARDS


def get_seeded_violations() -> list[SeededViolation]:
    """Return the seeded-violation registry."""
    return SEEDED_VIOLATIONS


def all_requirement_texts() -> dict[str, str]:
    """Map every requirement ID (system + domain) to its text.

    Used by the smell-quality test and by paper-facing tables.
    """
    texts: dict[str, str] = {r.req_id: r.text for r in SYSTEM_REQUIREMENTS}
    texts.update({r.req_id: r.text for r in DOMAIN_REQUIREMENTS})
    return texts


def dataset_stats() -> dict:
    """Return summary statistics of the UAV cross-domain dataset."""
    return {
        "system_requirements": len(SYSTEM_REQUIREMENTS),
        "hlr_requirements": len(get_hlr_requirements()),
        "hwr_requirements": len(get_hwr_requirements()),
        "total_requirements": len(SYSTEM_REQUIREMENTS) + len(DOMAIN_REQUIREMENTS),
        "interfaces": len(INTERFACES),
        "hazards": len(HAZARDS),
        "seeded_violations": len(SEEDED_VIOLATIONS),
    }


if __name__ == "__main__":
    stats = dataset_stats()
    print("UAV Cross-Domain Dataset Statistics")
    print("=" * 50)
    for key, value in stats.items():
        print(f"{key}: {value}")
    print()
    print("Seeded violations:")
    for sv in SEEDED_VIOLATIONS:
        print(f"  [{sv.objective_id}] {sv.key}: flags {sv.violating_element}, "
              f"clean twin {sv.compliant_counterpart}")
