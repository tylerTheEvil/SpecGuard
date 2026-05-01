"""CVA6 Requirements Dataset.

Extracted from the official CVA6 Requirements Specification, Revision 1.0.1,
curated by Jerome Quevremont (Thales) for OpenHW Group.

Source: https://docs.openhwgroup.org/projects/cva6-user-manual/02_cva6_requirements/cva6_requirements_specification.html
License: Apache-2.0 WITH SHL-2.1
Copyright: 2022 OpenHW Group and Thales, 2018 ETH Zurich and University of Bologna

This dataset is used as a benchmark for requirements quality analysis in the
SpecGuard prototype. CVA6 is selected as a primary benchmark because:

1. Industrial-grade requirements (curated by Thales — aerospace company)
2. Structured format with explicit IDs (GEN, ISA, PVL, etc.)
3. Uses standard "shall" / "should" / "may" modality
4. Specification text explicitly mentions "safety-critical applications"
5. Has accompanying SystemVerilog implementation for traceability
6. Open license allows research reuse
"""

from dataclasses import dataclass


@dataclass
class Requirement:
    """A single requirement extracted from CVA6 specification."""

    req_id: str
    text: str
    category: str
    safety_critical_context: bool = False
    parent_section: str = ""
    notes: str = ""


# Extracted from CVA6 Requirements Specification v1.0.1
# All requirements are functional and design-level; we keep them verbatim
# to preserve the original wording for smell analysis.
CVA6_REQUIREMENTS: list[Requirement] = [
    # === General requirement ===
    Requirement(
        req_id="GEN-10",
        text="CVA6 shall be fully compliant with RISC-V specifications [RVunpriv], "
        "[RVpriv] and [RVdbg] by implementing all mandatory features for the set of "
        "extensions that are selected and by passing [RVcompat] compatibility tests.",
        category="General",
        parent_section="Functional requirements",
    ),
    # === RISC-V standard instructions ===
    Requirement(
        req_id="ISA-10",
        text="CV64A6 shall support RV64I base instruction set, version 2.1.",
        category="ISA",
        parent_section="RISC-V standard instructions",
    ),
    Requirement(
        req_id="ISA-20",
        text="CV32A6 shall support RV32I base instruction set, version 2.1.",
        category="ISA",
        parent_section="RISC-V standard instructions",
    ),
    Requirement(
        req_id="ISA-30",
        text="CVA6 shall support the M extension (integer multiply and divide), version 2.0.",
        category="ISA",
        parent_section="RISC-V standard instructions",
    ),
    Requirement(
        req_id="ISA-40",
        text="CVA6 shall support the A extension (atomic instructions), version 2.1.",
        category="ISA",
        parent_section="RISC-V standard instructions",
    ),
    Requirement(
        req_id="ISA-50",
        text="CV32A6 shall support as an option the F extension (single-precision "
        "floating-point), version 2.2.",
        category="ISA",
        parent_section="RISC-V standard instructions",
    ),
    Requirement(
        req_id="ISA-60",
        text="CV64A6 shall support as an option the F and D extensions (single- and "
        "double-precision floating-point), version 2.2.",
        category="ISA",
        parent_section="RISC-V standard instructions",
    ),
    Requirement(
        req_id="ISA-70",
        text="CV64A6 shall support as an option the F extension (single-precision "
        "without double-precision floating-point), version 2.2.",
        category="ISA",
        parent_section="RISC-V standard instructions",
    ),
    Requirement(
        req_id="ISA-80",
        text="CVA6 shall support as an option the C extension (compressed instructions), "
        "version 2.0.",
        category="ISA",
        parent_section="RISC-V standard instructions",
    ),
    Requirement(
        req_id="ISA-90",
        text="CVA6 shall support the Zicsr extension (CSR instructions), version 2.0.",
        category="ISA",
        parent_section="RISC-V standard instructions",
    ),
    Requirement(
        req_id="ISA-100",
        text="CVA6 shall support the Zifencei extension, version 2.0.",
        category="ISA",
        parent_section="RISC-V standard instructions",
    ),
    Requirement(
        req_id="ISA-120",
        text="CVA6 should support as an option the B extension (bit manipulation), "
        "version 1.0. The B extension comprises the Zba, Zbb, Zbc and Zbs extensions.",
        category="ISA",
        parent_section="RISC-V standard instructions",
    ),
    Requirement(
        req_id="ISA-130",
        text="CVA6 should support as an option the Zicond extension (ratification "
        "pending) version 1.0.",
        category="ISA",
        parent_section="RISC-V standard instructions",
    ),
    Requirement(
        req_id="ISA-140",
        text="CVA6 should support as an option the Zcb extension version 1.0.",
        category="ISA",
        parent_section="RISC-V standard instructions",
    ),
    Requirement(
        req_id="ISA-150",
        text="CVA6 should support as an option the Zcmp extension version 1.0.",
        category="ISA",
        parent_section="RISC-V standard instructions",
    ),
    # === Privileges and virtual memory ===
    Requirement(
        req_id="PVL-10",
        text="CVA6 shall support machine, supervisor, user and debug privilege modes.",
        category="Privileges",
        parent_section="Privileges and virtual memory",
    ),
    Requirement(
        req_id="PVL-20",
        text="CV64A6 shall support as an option the Sv39 virtual memory, version 1.11.",
        category="Privileges",
        parent_section="Privileges and virtual memory",
    ),
    Requirement(
        req_id="PVL-30",
        text="CV32A6 shall support as an option the Sv32 virtual memory version 1.11.",
        category="Privileges",
        parent_section="Privileges and virtual memory",
    ),
    Requirement(
        req_id="PVL-40",
        text="CVA6 instances that do not feature virtual memory shall support the Bare mode.",
        category="Privileges",
        parent_section="Privileges and virtual memory",
    ),
    Requirement(
        req_id="PVL-50",
        text="CVA6 shall feature PMP (physical memory protection) as an option.",
        category="Privileges",
        parent_section="Privileges and virtual memory",
    ),
    Requirement(
        req_id="PVL-60",
        text="CV64A6 shall support as an option the H extension (hypervisor) version 1.0.",
        category="Privileges",
        parent_section="Privileges and virtual memory",
    ),
    # === Performance counters ===
    Requirement(
        req_id="HPM-10",
        text="CVA6 shall implement the 64-bit mcycle and minstret standard performance "
        "counters (including their upper 32 bits counterparts mcycleh and minstreth in "
        "CV32A6) as per [RVpriv].",
        category="Performance",
        safety_critical_context=True,
        parent_section="Performance counters",
        notes="Section explicitly mentioned as safety-critical relevance",
    ),
    Requirement(
        req_id="HPM-20",
        text="CVA6 shall implement as an option six generic 64-bit performance counters "
        "located in hpmcounter3 to hpmcounter8 (including their upper 32 bits counterparts "
        "in CV32A6: hpmcounter3h to hpmcounter8h).",
        category="Performance",
        safety_critical_context=True,
        parent_section="Performance counters",
    ),
    Requirement(
        req_id="HPM-30",
        text="Each of the six generic performance counters shall be able to count "
        "events from one of these sources: L1 I-Cache misses, L1 D-Cache misses, "
        "ITLB misses, DTLB misses, Load accesses, Store accesses, Exceptions, "
        "Exception handler returns, Branch instructions, Branch mispredicts, "
        "Branch exceptions, Call, Return, MSB Full, Instruction fetch Empty, "
        "L1 I-Cache accesses, L1 D-Cache accesses, L1$ line invalidation, I-TLB flush, "
        "Integer instructions, Floating point instructions, Pipeline bubbles.",
        category="Performance",
        safety_critical_context=True,
        parent_section="Performance counters",
    ),
    Requirement(
        req_id="HPM-40",
        text="The source of events counted by the six generic performance counters "
        "shall be selected by the mhpmevent3 to mhpmevent8 CSRs.",
        category="Performance",
        safety_critical_context=True,
        parent_section="Performance counters",
    ),
    Requirement(
        req_id="HPM-50",
        text="CVA6 shall allow the supervisor access of performance counters through "
        "enabling of mcounteren CSR.",
        category="Performance",
        parent_section="Performance counters",
    ),
    Requirement(
        req_id="HPM-60",
        text="CVA6 shall allow the user access of performance counters through "
        "enabling of scounteren CSR.",
        category="Performance",
        parent_section="Performance counters",
    ),
    Requirement(
        req_id="HPM-70",
        text="CVA6 shall implement the mcountinhibit counter-inhibit register.",
        category="Performance",
        parent_section="Performance counters",
    ),
    Requirement(
        req_id="HPM-80",
        text="CVA6 shall implement the read-only cycle, instret, hpmcounter3 to "
        "hpmcounter8 access to counters (and their upper 32-bit counterparts in CV32A6).",
        category="Performance",
        parent_section="Performance counters",
    ),
    # === L1 write-through data cache ===
    Requirement(
        req_id="L1W-10",
        text="L1WTD shall reflect all write accesses (stores) by the CVA6 core to the "
        "external memory within an upper-bounded number of cycles. The upper-bound is "
        "fixed but not specified here.",
        category="Cache",
        safety_critical_context=True,
        parent_section="L1 write-through data cache",
        notes="Section header mentions safety-critical timing predictability",
    ),
    Requirement(
        req_id="L1W-20",
        text="L1WTD shall not change the order of write accesses to the external memory "
        "with respect to the order of write accesses (stores) received from the CVA6 core.",
        category="Cache",
        safety_critical_context=True,
        parent_section="L1 write-through data cache",
    ),
    Requirement(
        req_id="L1W-30",
        text="L1WTD should offer the following size/ways configurations: 0 kbyte (no cache), "
        "4 kbytes (4 or 8 ways), 8 kbytes (4, 8 or 16 ways), 16 kbytes (4, 8 or 16 ways), "
        "32 kbytes (8 or 16 ways).",
        category="Cache",
        safety_critical_context=True,
        parent_section="L1 write-through data cache",
    ),
    Requirement(
        req_id="L1W-40",
        text="L1WTD shall support datasize extension to store EDC, ECC or other "
        "information. The numbers of bits of the extension is defined by a "
        "compile-time parameter.",
        category="Cache",
        safety_critical_context=True,
        parent_section="L1 write-through data cache",
    ),
    Requirement(
        req_id="L1W-50",
        text="To interface with the P-Mesh coherence system of OpenPiton, L1WTD shall "
        "have a line invalidate external command that invalidates the content of a "
        "line upon request.",
        category="Cache",
        parent_section="L1 write-through data cache",
    ),
    Requirement(
        req_id="L1W-60",
        text="Some physical memory regions shall be configurable as not L1WTD cacheable "
        "at design time.",
        category="Cache",
        parent_section="L1 write-through data cache",
    ),
    Requirement(
        req_id="L1W-70",
        text="It shall be possible to invalidate L1WTD content with the FENCE.T command.",
        category="Cache",
        parent_section="L1 write-through data cache",
    ),
    Requirement(
        req_id="L1W-80",
        text="The replacement policy of L1WTD shall be LFSR (pseudo-random) or LRU "
        "(least recently used).",
        category="Cache",
        parent_section="L1 write-through data cache",
    ),
    Requirement(
        req_id="L1W-90",
        text="L1WTD should offer a feature to transform cache ways into a scratchpad. "
        "Alternatively, this requirement can be realized with a separate scratchpad.",
        category="Cache",
        parent_section="L1 write-through data cache",
    ),
    Requirement(
        req_id="L1W-100",
        text="A custom CSR shall allow to disable or enable L1WTD.",
        category="Cache",
        parent_section="L1 write-through data cache",
    ),
    # === L1 Instruction cache ===
    Requirement(
        req_id="L1I-10",
        text="L1I should offer the following size/ways configurations: 4 kbytes: 3, 4 "
        "or 8 ways, 8 kbytes: 4, 8, or 16 ways, 16 kbytes: 4, 8 or 16 ways, "
        "32 kbytes: 8 or 16 ways.",
        category="Cache",
        safety_critical_context=True,
        parent_section="L1 Instruction cache",
    ),
    Requirement(
        req_id="L1I-20",
        text="L1I shall support datasize extension to store EDC, ECC or other "
        "information. The numbers of bits of the extension is defined by a "
        "compile-time parameter.",
        category="Cache",
        safety_critical_context=True,
        parent_section="L1 Instruction cache",
    ),
    Requirement(
        req_id="L1I-30",
        text="To interface with the P-Mesh coherence system of OpenPiton, L1I shall have "
        "a line invalidate external command that invalidates the content of a line upon request.",
        category="Cache",
        parent_section="L1 Instruction cache",
    ),
    Requirement(
        req_id="L1I-40",
        text="It shall be possible to invalidate L1I content with the FENCE.T command.",
        category="Cache",
        parent_section="L1 Instruction cache",
    ),
    Requirement(
        req_id="L1I-50",
        text="The replacement policy of L1I shall be LFSR (pseudo-random) or LRU "
        "(least recently used).",
        category="Cache",
        parent_section="L1 Instruction cache",
    ),
    Requirement(
        req_id="L1I-60",
        text="L1I should offer a feature to transform cache ways into a scratchpad. "
        "Alternatively, this requirement can be realized with a separate scratchpad.",
        category="Cache",
        parent_section="L1 Instruction cache",
    ),
    Requirement(
        req_id="L1I-70",
        text="A custom CSR shall allow to disable or enable L1I.",
        category="Cache",
        parent_section="L1 Instruction cache",
    ),
    # === FENCE.T custom instruction ===
    Requirement(
        req_id="FET-10",
        text="CVA6 should support the FENCE.T instruction that ensures that the "
        "execution time of subsequent instructions is unrelated with predecessor "
        "instructions.",
        category="Instruction",
        safety_critical_context=True,
        parent_section="FENCE.T custom instruction",
        notes="SPECTRE countermeasure, useful for safety-critical timing predictability",
    ),
    Requirement(
        req_id="FET-20",
        text="FENCE.T should be available in all privilege modes (machine, supervisor, "
        "user and hypervisor if present).",
        category="Instruction",
        safety_critical_context=True,
        parent_section="FENCE.T custom instruction",
    ),
    # === PPA targets ===
    Requirement(
        req_id="PPA-10",
        text="CVA6 should be resource-optimized on FPGA and ASIC targets.",
        category="PPA",
        parent_section="PPA targets",
    ),
    Requirement(
        req_id="PPA-20",
        text="CVA6 should deliver more than 2.1 CoreMark/MHz.",
        category="PPA",
        parent_section="PPA targets",
    ),
    Requirement(
        req_id="PPA-30",
        text="CV32A6 should run at more than 150 MHz in the cv32a6_imac_sv32 "
        "configuration on Kintex 7 FPGA technology, commercial -2 speed grade.",
        category="PPA",
        parent_section="PPA targets",
    ),
    Requirement(
        req_id="PPA-40",
        text="CV64A6 should run at more than 900 MHz in the cv64a6_imacfd_sv39 "
        "configuration on 28FDSOI technology in the worst case frequency corner with "
        "the fastest threshold voltage.",
        category="PPA",
        parent_section="PPA targets",
    ),
    Requirement(
        req_id="PPA-50",
        text="TBD: Placeholder for single-precision floating performance per MHz.",
        category="PPA",
        parent_section="PPA targets",
        notes="Placeholder requirement — known incomplete by spec authors",
    ),
    Requirement(
        req_id="PPA-60",
        text="TBD: Placeholder for double-precision floating performance per MHz.",
        category="PPA",
        parent_section="PPA targets",
        notes="Placeholder requirement — known incomplete by spec authors",
    ),
    # === Interface requirements ===
    Requirement(
        req_id="MEM-10",
        text="CVA6 memory interface shall comply with AXI5 specification including the "
        "Atomic_Transactions property support as defined in [AXI] section E1.1.",
        category="Interface",
        parent_section="Memory bus",
    ),
    Requirement(
        req_id="MEM-20",
        text="CVA6 AXI memory interface shall feature user bit extensions on the data "
        "bus (WUSER and RUSER as per [AXI]) in connection with the L1I and L1WTD "
        "datasize extensions, with a number of user bits greater or equal to 0.",
        category="Interface",
        parent_section="Memory bus",
    ),
    Requirement(
        req_id="DBG-10",
        text="CVA6 shall implement both the Abstracted Command and Execution based "
        "features outlined in chapter 4 of [RVdbg].",
        category="Interface",
        parent_section="Debug",
    ),
    Requirement(
        req_id="IRQ-10",
        text="CVA6 shall implement interrupt handling registers as per the RISC-V "
        "privilege specification and interface with a CLINT implementation.",
        category="Interface",
        parent_section="Interrupts",
    ),
    Requirement(
        req_id="XIF-10",
        text="To extend the supported instructions, CVA6 shall have a coprocessor "
        "interface that supports the Issue, Commit and Result interfaces of the "
        "[CV-X-IF] specification.",
        category="Interface",
        parent_section="Coprocessor interface",
    ),
    Requirement(
        req_id="TRI-10",
        text="CVA6 shall have the Transaction-Response Interface (TRI) needed to "
        "interface with the P-Mesh coherence system of OpenPiton, according to "
        "[OpenPiton].",
        category="Interface",
        parent_section="Multi-core interface",
    ),
    # === Design rules ===
    Requirement(
        req_id="RUL-10",
        text="CVA6 should have a configurable reset signal: synchronous/asynchronous, "
        "active on high or low levels.",
        category="Design",
        parent_section="Design rules",
    ),
    Requirement(
        req_id="RUL-20",
        text="CVA6 shall be a super-synchronous design with a single clock input.",
        category="Design",
        parent_section="Design rules",
    ),
    Requirement(
        req_id="RUL-30",
        text="CVA6 should not include multi-cycle paths.",
        category="Design",
        parent_section="Design rules",
    ),
    Requirement(
        req_id="RUL-40",
        text="CVA6 should not include technology-dependent blocks.",
        category="Design",
        parent_section="Design rules",
    ),
]


def get_all_requirements() -> list[Requirement]:
    """Return all CVA6 requirements."""
    return CVA6_REQUIREMENTS


def get_safety_critical_requirements() -> list[Requirement]:
    """Return only requirements marked as safety-critical context."""
    return [r for r in CVA6_REQUIREMENTS if r.safety_critical_context]


def get_by_category(category: str) -> list[Requirement]:
    """Return requirements filtered by category."""
    return [r for r in CVA6_REQUIREMENTS if r.category == category]


def dataset_stats() -> dict:
    """Return summary statistics of the dataset."""
    categories: dict[str, int] = {}
    for req in CVA6_REQUIREMENTS:
        categories[req.category] = categories.get(req.category, 0) + 1

    return {
        "total_requirements": len(CVA6_REQUIREMENTS),
        "safety_critical_count": sum(
            1 for r in CVA6_REQUIREMENTS if r.safety_critical_context
        ),
        "by_category": categories,
        "shall_count": sum(1 for r in CVA6_REQUIREMENTS if " shall " in r.text),
        "should_count": sum(1 for r in CVA6_REQUIREMENTS if " should " in r.text),
        "tbd_count": sum(1 for r in CVA6_REQUIREMENTS if r.text.startswith("TBD")),
    }


if __name__ == "__main__":
    stats = dataset_stats()
    print("CVA6 Requirements Dataset Statistics")
    print("=" * 50)
    for key, value in stats.items():
        print(f"{key}: {value}")
