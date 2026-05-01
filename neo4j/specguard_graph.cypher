// =========================================================
// SpecGuard Knowledge Graph — CVA6 Requirements
// =========================================================
// 
// Auto-generated from CVA6 Requirements Specification v1.0.1
// Source: https://docs.openhwgroup.org/projects/cva6-user-manual/
// 
// To execute:
//   1. Open Neo4j Browser (http://localhost:7474)
//   2. Paste this script and run with the play button
//   OR
//   $ cypher-shell -u neo4j -p <password> < specguard_graph.cypher
// =========================================================

// Clean any previous SpecGuard data (comment out to keep)
MATCH (n) WHERE n:Requirement OR n:Category OR n:Component OR
              n:Standard OR n:Configuration OR n:Smell
DETACH DELETE n;

// ---- Indexes ----
CREATE INDEX requirement_id IF NOT EXISTS FOR (r:Requirement) ON (r.req_id);
CREATE INDEX category_name IF NOT EXISTS FOR (c:Category) ON (c.name);
CREATE INDEX component_name IF NOT EXISTS FOR (c:Component) ON (c.name);
CREATE INDEX standard_name IF NOT EXISTS FOR (s:Standard) ON (s.name);

// ---- Requirement nodes (64) ----
MERGE (n:Requirement {node_id: 'GEN-10'}) SET n += {req_id: 'GEN-10', text: 'CVA6 shall be fully compliant with RISC-V specifications [RVunpriv], [RVpriv] and [RVdbg] by implementing all mandatory features for the set of extensions that are selected and by passing [RVcompat] compatibility tests.', category: 'General', parent_section: 'Functional requirements', safety_critical: false, modal_strength: 'mandatory', token_count: 31, notes: ''};
MERGE (n:Requirement {node_id: 'ISA-10'}) SET n += {req_id: 'ISA-10', text: 'CV64A6 shall support RV64I base instruction set, version 2.1.', category: 'ISA', parent_section: 'RISC-V standard instructions', safety_critical: false, modal_strength: 'mandatory', token_count: 9, notes: ''};
MERGE (n:Requirement {node_id: 'ISA-20'}) SET n += {req_id: 'ISA-20', text: 'CV32A6 shall support RV32I base instruction set, version 2.1.', category: 'ISA', parent_section: 'RISC-V standard instructions', safety_critical: false, modal_strength: 'mandatory', token_count: 9, notes: ''};
MERGE (n:Requirement {node_id: 'ISA-30'}) SET n += {req_id: 'ISA-30', text: 'CVA6 shall support the M extension (integer multiply and divide), version 2.0.', category: 'ISA', parent_section: 'RISC-V standard instructions', safety_critical: false, modal_strength: 'mandatory', token_count: 12, notes: ''};
MERGE (n:Requirement {node_id: 'ISA-40'}) SET n += {req_id: 'ISA-40', text: 'CVA6 shall support the A extension (atomic instructions), version 2.1.', category: 'ISA', parent_section: 'RISC-V standard instructions', safety_critical: false, modal_strength: 'mandatory', token_count: 10, notes: ''};
MERGE (n:Requirement {node_id: 'ISA-50'}) SET n += {req_id: 'ISA-50', text: 'CV32A6 shall support as an option the F extension (single-precision floating-point), version 2.2.', category: 'ISA', parent_section: 'RISC-V standard instructions', safety_critical: false, modal_strength: 'mandatory', token_count: 13, notes: ''};
MERGE (n:Requirement {node_id: 'ISA-60'}) SET n += {req_id: 'ISA-60', text: 'CV64A6 shall support as an option the F and D extensions (single- and double-precision floating-point), version 2.2.', category: 'ISA', parent_section: 'RISC-V standard instructions', safety_critical: false, modal_strength: 'mandatory', token_count: 17, notes: ''};
MERGE (n:Requirement {node_id: 'ISA-70'}) SET n += {req_id: 'ISA-70', text: 'CV64A6 shall support as an option the F extension (single-precision without double-precision floating-point), version 2.2.', category: 'ISA', parent_section: 'RISC-V standard instructions', safety_critical: false, modal_strength: 'mandatory', token_count: 15, notes: ''};
MERGE (n:Requirement {node_id: 'ISA-80'}) SET n += {req_id: 'ISA-80', text: 'CVA6 shall support as an option the C extension (compressed instructions), version 2.0.', category: 'ISA', parent_section: 'RISC-V standard instructions', safety_critical: false, modal_strength: 'mandatory', token_count: 13, notes: ''};
MERGE (n:Requirement {node_id: 'ISA-90'}) SET n += {req_id: 'ISA-90', text: 'CVA6 shall support the Zicsr extension (CSR instructions), version 2.0.', category: 'ISA', parent_section: 'RISC-V standard instructions', safety_critical: false, modal_strength: 'mandatory', token_count: 10, notes: ''};
MERGE (n:Requirement {node_id: 'ISA-100'}) SET n += {req_id: 'ISA-100', text: 'CVA6 shall support the Zifencei extension, version 2.0.', category: 'ISA', parent_section: 'RISC-V standard instructions', safety_critical: false, modal_strength: 'mandatory', token_count: 8, notes: ''};
MERGE (n:Requirement {node_id: 'ISA-120'}) SET n += {req_id: 'ISA-120', text: 'CVA6 should support as an option the B extension (bit manipulation), version 1.0. The B extension comprises the Zba, Zbb, Zbc and Zbs extensions.', category: 'ISA', parent_section: 'RISC-V standard instructions', safety_critical: false, modal_strength: 'recommended', token_count: 24, notes: ''};
MERGE (n:Requirement {node_id: 'ISA-130'}) SET n += {req_id: 'ISA-130', text: 'CVA6 should support as an option the Zicond extension (ratification pending) version 1.0.', category: 'ISA', parent_section: 'RISC-V standard instructions', safety_critical: false, modal_strength: 'recommended', token_count: 13, notes: ''};
MERGE (n:Requirement {node_id: 'ISA-140'}) SET n += {req_id: 'ISA-140', text: 'CVA6 should support as an option the Zcb extension version 1.0.', category: 'ISA', parent_section: 'RISC-V standard instructions', safety_critical: false, modal_strength: 'recommended', token_count: 11, notes: ''};
MERGE (n:Requirement {node_id: 'ISA-150'}) SET n += {req_id: 'ISA-150', text: 'CVA6 should support as an option the Zcmp extension version 1.0.', category: 'ISA', parent_section: 'RISC-V standard instructions', safety_critical: false, modal_strength: 'recommended', token_count: 11, notes: ''};
MERGE (n:Requirement {node_id: 'PVL-10'}) SET n += {req_id: 'PVL-10', text: 'CVA6 shall support machine, supervisor, user and debug privilege modes.', category: 'Privileges', parent_section: 'Privileges and virtual memory', safety_critical: false, modal_strength: 'mandatory', token_count: 10, notes: ''};
MERGE (n:Requirement {node_id: 'PVL-20'}) SET n += {req_id: 'PVL-20', text: 'CV64A6 shall support as an option the Sv39 virtual memory, version 1.11.', category: 'Privileges', parent_section: 'Privileges and virtual memory', safety_critical: false, modal_strength: 'mandatory', token_count: 12, notes: ''};
MERGE (n:Requirement {node_id: 'PVL-30'}) SET n += {req_id: 'PVL-30', text: 'CV32A6 shall support as an option the Sv32 virtual memory version 1.11.', category: 'Privileges', parent_section: 'Privileges and virtual memory', safety_critical: false, modal_strength: 'mandatory', token_count: 12, notes: ''};
MERGE (n:Requirement {node_id: 'PVL-40'}) SET n += {req_id: 'PVL-40', text: 'CVA6 instances that do not feature virtual memory shall support the Bare mode.', category: 'Privileges', parent_section: 'Privileges and virtual memory', safety_critical: false, modal_strength: 'mandatory', token_count: 13, notes: ''};
MERGE (n:Requirement {node_id: 'PVL-50'}) SET n += {req_id: 'PVL-50', text: 'CVA6 shall feature PMP (physical memory protection) as an option.', category: 'Privileges', parent_section: 'Privileges and virtual memory', safety_critical: false, modal_strength: 'mandatory', token_count: 10, notes: ''};
MERGE (n:Requirement {node_id: 'PVL-60'}) SET n += {req_id: 'PVL-60', text: 'CV64A6 shall support as an option the H extension (hypervisor) version 1.0.', category: 'Privileges', parent_section: 'Privileges and virtual memory', safety_critical: false, modal_strength: 'mandatory', token_count: 12, notes: ''};
MERGE (n:Requirement {node_id: 'HPM-10'}) SET n += {req_id: 'HPM-10', text: 'CVA6 shall implement the 64-bit mcycle and minstret standard performance counters (including their upper 32 bits counterparts mcycleh and minstreth in CV32A6) as per [RVpriv].', category: 'Performance', parent_section: 'Performance counters', safety_critical: true, modal_strength: 'mandatory', token_count: 25, notes: 'Section explicitly mentioned as safety-critical relevance'};
MERGE (n:Requirement {node_id: 'HPM-20'}) SET n += {req_id: 'HPM-20', text: 'CVA6 shall implement as an option six generic 64-bit performance counters located in hpmcounter3 to hpmcounter8 (including their upper 32 bits counterparts in CV32A6: hpmcounter3h to hpmcounter8h).', category: 'Performance', parent_section: 'Performance counters', safety_critical: true, modal_strength: 'mandatory', token_count: 27, notes: ''};
MERGE (n:Requirement {node_id: 'HPM-30'}) SET n += {req_id: 'HPM-30', text: 'Each of the six generic performance counters shall be able to count events from one of these sources: L1 I-Cache misses, L1 D-Cache misses, ITLB misses, DTLB misses, Load accesses, Store accesses, Exceptions, Exception handler returns, Branch instructions, Branch mispredicts, Branch exceptions, Call, Return, MSB Full, Instruction fetch Empty, L1 I-Cache accesses, L1 D-Cache accesses, L1$ line invalidation, I-TLB flush, Integer instructions, Floating point instructions, Pipeline bubbles.', category: 'Performance', parent_section: 'Performance counters', safety_critical: true, modal_strength: 'mandatory', token_count: 67, notes: ''};
MERGE (n:Requirement {node_id: 'HPM-40'}) SET n += {req_id: 'HPM-40', text: 'The source of events counted by the six generic performance counters shall be selected by the mhpmevent3 to mhpmevent8 CSRs.', category: 'Performance', parent_section: 'Performance counters', safety_critical: true, modal_strength: 'mandatory', token_count: 20, notes: ''};
MERGE (n:Requirement {node_id: 'HPM-50'}) SET n += {req_id: 'HPM-50', text: 'CVA6 shall allow the supervisor access of performance counters through enabling of mcounteren CSR.', category: 'Performance', parent_section: 'Performance counters', safety_critical: false, modal_strength: 'mandatory', token_count: 14, notes: ''};
MERGE (n:Requirement {node_id: 'HPM-60'}) SET n += {req_id: 'HPM-60', text: 'CVA6 shall allow the user access of performance counters through enabling of scounteren CSR.', category: 'Performance', parent_section: 'Performance counters', safety_critical: false, modal_strength: 'mandatory', token_count: 14, notes: ''};
MERGE (n:Requirement {node_id: 'HPM-70'}) SET n += {req_id: 'HPM-70', text: 'CVA6 shall implement the mcountinhibit counter-inhibit register.', category: 'Performance', parent_section: 'Performance counters', safety_critical: false, modal_strength: 'mandatory', token_count: 7, notes: ''};
MERGE (n:Requirement {node_id: 'HPM-80'}) SET n += {req_id: 'HPM-80', text: 'CVA6 shall implement the read-only cycle, instret, hpmcounter3 to hpmcounter8 access to counters (and their upper 32-bit counterparts in CV32A6).', category: 'Performance', parent_section: 'Performance counters', safety_critical: false, modal_strength: 'mandatory', token_count: 20, notes: ''};
MERGE (n:Requirement {node_id: 'L1W-10'}) SET n += {req_id: 'L1W-10', text: 'L1WTD shall reflect all write accesses (stores) by the CVA6 core to the external memory within an upper-bounded number of cycles. The upper-bound is fixed but not specified here.', category: 'Cache', parent_section: 'L1 write-through data cache', safety_critical: true, modal_strength: 'mandatory', token_count: 29, notes: 'Section header mentions safety-critical timing predictability'};
MERGE (n:Requirement {node_id: 'L1W-20'}) SET n += {req_id: 'L1W-20', text: 'L1WTD shall not change the order of write accesses to the external memory with respect to the order of write accesses (stores) received from the CVA6 core.', category: 'Cache', parent_section: 'L1 write-through data cache', safety_critical: true, modal_strength: 'mandatory', token_count: 27, notes: ''};
MERGE (n:Requirement {node_id: 'L1W-30'}) SET n += {req_id: 'L1W-30', text: 'L1WTD should offer the following size/ways configurations: 0 kbyte (no cache), 4 kbytes (4 or 8 ways), 8 kbytes (4, 8 or 16 ways), 16 kbytes (4, 8 or 16 ways), 32 kbytes (8 or 16 ways).', category: 'Cache', parent_section: 'L1 write-through data cache', safety_critical: true, modal_strength: 'recommended', token_count: 37, notes: ''};
MERGE (n:Requirement {node_id: 'L1W-40'}) SET n += {req_id: 'L1W-40', text: 'L1WTD shall support datasize extension to store EDC, ECC or other information. The numbers of bits of the extension is defined by a compile-time parameter.', category: 'Cache', parent_section: 'L1 write-through data cache', safety_critical: true, modal_strength: 'mandatory', token_count: 25, notes: ''};
MERGE (n:Requirement {node_id: 'L1W-50'}) SET n += {req_id: 'L1W-50', text: 'To interface with the P-Mesh coherence system of OpenPiton, L1WTD shall have a line invalidate external command that invalidates the content of a line upon request.', category: 'Cache', parent_section: 'L1 write-through data cache', safety_critical: false, modal_strength: 'mandatory', token_count: 26, notes: ''};
MERGE (n:Requirement {node_id: 'L1W-60'}) SET n += {req_id: 'L1W-60', text: 'Some physical memory regions shall be configurable as not L1WTD cacheable at design time.', category: 'Cache', parent_section: 'L1 write-through data cache', safety_critical: false, modal_strength: 'mandatory', token_count: 14, notes: ''};
MERGE (n:Requirement {node_id: 'L1W-70'}) SET n += {req_id: 'L1W-70', text: 'It shall be possible to invalidate L1WTD content with the FENCE.T command.', category: 'Cache', parent_section: 'L1 write-through data cache', safety_critical: false, modal_strength: 'mandatory', token_count: 12, notes: ''};
MERGE (n:Requirement {node_id: 'L1W-80'}) SET n += {req_id: 'L1W-80', text: 'The replacement policy of L1WTD shall be LFSR (pseudo-random) or LRU (least recently used).', category: 'Cache', parent_section: 'L1 write-through data cache', safety_critical: false, modal_strength: 'mandatory', token_count: 14, notes: ''};
MERGE (n:Requirement {node_id: 'L1W-90'}) SET n += {req_id: 'L1W-90', text: 'L1WTD should offer a feature to transform cache ways into a scratchpad. Alternatively, this requirement can be realized with a separate scratchpad.', category: 'Cache', parent_section: 'L1 write-through data cache', safety_critical: false, modal_strength: 'recommended', token_count: 22, notes: ''};
MERGE (n:Requirement {node_id: 'L1W-100'}) SET n += {req_id: 'L1W-100', text: 'A custom CSR shall allow to disable or enable L1WTD.', category: 'Cache', parent_section: 'L1 write-through data cache', safety_critical: false, modal_strength: 'mandatory', token_count: 10, notes: ''};
MERGE (n:Requirement {node_id: 'L1I-10'}) SET n += {req_id: 'L1I-10', text: 'L1I should offer the following size/ways configurations: 4 kbytes: 3, 4 or 8 ways, 8 kbytes: 4, 8, or 16 ways, 16 kbytes: 4, 8 or 16 ways, 32 kbytes: 8 or 16 ways.', category: 'Cache', parent_section: 'L1 Instruction cache', safety_critical: true, modal_strength: 'recommended', token_count: 34, notes: ''};
MERGE (n:Requirement {node_id: 'L1I-20'}) SET n += {req_id: 'L1I-20', text: 'L1I shall support datasize extension to store EDC, ECC or other information. The numbers of bits of the extension is defined by a compile-time parameter.', category: 'Cache', parent_section: 'L1 Instruction cache', safety_critical: true, modal_strength: 'mandatory', token_count: 25, notes: ''};
MERGE (n:Requirement {node_id: 'L1I-30'}) SET n += {req_id: 'L1I-30', text: 'To interface with the P-Mesh coherence system of OpenPiton, L1I shall have a line invalidate external command that invalidates the content of a line upon request.', category: 'Cache', parent_section: 'L1 Instruction cache', safety_critical: false, modal_strength: 'mandatory', token_count: 26, notes: ''};
MERGE (n:Requirement {node_id: 'L1I-40'}) SET n += {req_id: 'L1I-40', text: 'It shall be possible to invalidate L1I content with the FENCE.T command.', category: 'Cache', parent_section: 'L1 Instruction cache', safety_critical: false, modal_strength: 'mandatory', token_count: 12, notes: ''};
MERGE (n:Requirement {node_id: 'L1I-50'}) SET n += {req_id: 'L1I-50', text: 'The replacement policy of L1I shall be LFSR (pseudo-random) or LRU (least recently used).', category: 'Cache', parent_section: 'L1 Instruction cache', safety_critical: false, modal_strength: 'mandatory', token_count: 14, notes: ''};
MERGE (n:Requirement {node_id: 'L1I-60'}) SET n += {req_id: 'L1I-60', text: 'L1I should offer a feature to transform cache ways into a scratchpad. Alternatively, this requirement can be realized with a separate scratchpad.', category: 'Cache', parent_section: 'L1 Instruction cache', safety_critical: false, modal_strength: 'recommended', token_count: 22, notes: ''};
MERGE (n:Requirement {node_id: 'L1I-70'}) SET n += {req_id: 'L1I-70', text: 'A custom CSR shall allow to disable or enable L1I.', category: 'Cache', parent_section: 'L1 Instruction cache', safety_critical: false, modal_strength: 'mandatory', token_count: 10, notes: ''};
MERGE (n:Requirement {node_id: 'FET-10'}) SET n += {req_id: 'FET-10', text: 'CVA6 should support the FENCE.T instruction that ensures that the execution time of subsequent instructions is unrelated with predecessor instructions.', category: 'Instruction', parent_section: 'FENCE.T custom instruction', safety_critical: true, modal_strength: 'recommended', token_count: 20, notes: 'SPECTRE countermeasure, useful for safety-critical timing predictability'};
MERGE (n:Requirement {node_id: 'FET-20'}) SET n += {req_id: 'FET-20', text: 'FENCE.T should be available in all privilege modes (machine, supervisor, user and hypervisor if present).', category: 'Instruction', parent_section: 'FENCE.T custom instruction', safety_critical: true, modal_strength: 'recommended', token_count: 15, notes: ''};
MERGE (n:Requirement {node_id: 'PPA-10'}) SET n += {req_id: 'PPA-10', text: 'CVA6 should be resource-optimized on FPGA and ASIC targets.', category: 'PPA', parent_section: 'PPA targets', safety_critical: false, modal_strength: 'recommended', token_count: 9, notes: ''};
MERGE (n:Requirement {node_id: 'PPA-20'}) SET n += {req_id: 'PPA-20', text: 'CVA6 should deliver more than 2.1 CoreMark/MHz.', category: 'PPA', parent_section: 'PPA targets', safety_critical: false, modal_strength: 'recommended', token_count: 7, notes: ''};
MERGE (n:Requirement {node_id: 'PPA-30'}) SET n += {req_id: 'PPA-30', text: 'CV32A6 should run at more than 150 MHz in the cv32a6_imac_sv32 configuration on Kintex 7 FPGA technology, commercial -2 speed grade.', category: 'PPA', parent_section: 'PPA targets', safety_critical: false, modal_strength: 'recommended', token_count: 21, notes: ''};
MERGE (n:Requirement {node_id: 'PPA-40'}) SET n += {req_id: 'PPA-40', text: 'CV64A6 should run at more than 900 MHz in the cv64a6_imacfd_sv39 configuration on 28FDSOI technology in the worst case frequency corner with the fastest threshold voltage.', category: 'PPA', parent_section: 'PPA targets', safety_critical: false, modal_strength: 'recommended', token_count: 26, notes: ''};
MERGE (n:Requirement {node_id: 'PPA-50'}) SET n += {req_id: 'PPA-50', text: 'TBD: Placeholder for single-precision floating performance per MHz.', category: 'PPA', parent_section: 'PPA targets', safety_critical: false, modal_strength: 'unspecified', token_count: 8, notes: 'Placeholder requirement — known incomplete by spec authors'};
MERGE (n:Requirement {node_id: 'PPA-60'}) SET n += {req_id: 'PPA-60', text: 'TBD: Placeholder for double-precision floating performance per MHz.', category: 'PPA', parent_section: 'PPA targets', safety_critical: false, modal_strength: 'unspecified', token_count: 8, notes: 'Placeholder requirement — known incomplete by spec authors'};
MERGE (n:Requirement {node_id: 'MEM-10'}) SET n += {req_id: 'MEM-10', text: 'CVA6 memory interface shall comply with AXI5 specification including the Atomic_Transactions property support as defined in [AXI] section E1.1.', category: 'Interface', parent_section: 'Memory bus', safety_critical: false, modal_strength: 'mandatory', token_count: 19, notes: ''};
MERGE (n:Requirement {node_id: 'MEM-20'}) SET n += {req_id: 'MEM-20', text: 'CVA6 AXI memory interface shall feature user bit extensions on the data bus (WUSER and RUSER as per [AXI]) in connection with the L1I and L1WTD datasize extensions, with a number of user bits greater or equal to 0.', category: 'Interface', parent_section: 'Memory bus', safety_critical: false, modal_strength: 'mandatory', token_count: 39, notes: ''};
MERGE (n:Requirement {node_id: 'DBG-10'}) SET n += {req_id: 'DBG-10', text: 'CVA6 shall implement both the Abstracted Command and Execution based features outlined in chapter 4 of [RVdbg].', category: 'Interface', parent_section: 'Debug', safety_critical: false, modal_strength: 'mandatory', token_count: 17, notes: ''};
MERGE (n:Requirement {node_id: 'IRQ-10'}) SET n += {req_id: 'IRQ-10', text: 'CVA6 shall implement interrupt handling registers as per the RISC-V privilege specification and interface with a CLINT implementation.', category: 'Interface', parent_section: 'Interrupts', safety_critical: false, modal_strength: 'mandatory', token_count: 18, notes: ''};
MERGE (n:Requirement {node_id: 'XIF-10'}) SET n += {req_id: 'XIF-10', text: 'To extend the supported instructions, CVA6 shall have a coprocessor interface that supports the Issue, Commit and Result interfaces of the [CV-X-IF] specification.', category: 'Interface', parent_section: 'Coprocessor interface', safety_critical: false, modal_strength: 'mandatory', token_count: 23, notes: ''};
MERGE (n:Requirement {node_id: 'TRI-10'}) SET n += {req_id: 'TRI-10', text: 'CVA6 shall have the Transaction-Response Interface (TRI) needed to interface with the P-Mesh coherence system of OpenPiton, according to [OpenPiton].', category: 'Interface', parent_section: 'Multi-core interface', safety_critical: false, modal_strength: 'mandatory', token_count: 20, notes: ''};
MERGE (n:Requirement {node_id: 'RUL-10'}) SET n += {req_id: 'RUL-10', text: 'CVA6 should have a configurable reset signal: synchronous/asynchronous, active on high or low levels.', category: 'Design', parent_section: 'Design rules', safety_critical: false, modal_strength: 'recommended', token_count: 14, notes: ''};
MERGE (n:Requirement {node_id: 'RUL-20'}) SET n += {req_id: 'RUL-20', text: 'CVA6 shall be a super-synchronous design with a single clock input.', category: 'Design', parent_section: 'Design rules', safety_critical: false, modal_strength: 'mandatory', token_count: 11, notes: ''};
MERGE (n:Requirement {node_id: 'RUL-30'}) SET n += {req_id: 'RUL-30', text: 'CVA6 should not include multi-cycle paths.', category: 'Design', parent_section: 'Design rules', safety_critical: false, modal_strength: 'recommended', token_count: 6, notes: ''};
MERGE (n:Requirement {node_id: 'RUL-40'}) SET n += {req_id: 'RUL-40', text: 'CVA6 should not include technology-dependent blocks.', category: 'Design', parent_section: 'Design rules', safety_critical: false, modal_strength: 'recommended', token_count: 6, notes: ''};

// ---- Category nodes (9) ----
MERGE (n:Category {node_id: 'General'}) SET n += {name: 'General'};
MERGE (n:Category {node_id: 'ISA'}) SET n += {name: 'ISA'};
MERGE (n:Category {node_id: 'Privileges'}) SET n += {name: 'Privileges'};
MERGE (n:Category {node_id: 'Performance'}) SET n += {name: 'Performance'};
MERGE (n:Category {node_id: 'Cache'}) SET n += {name: 'Cache'};
MERGE (n:Category {node_id: 'Instruction'}) SET n += {name: 'Instruction'};
MERGE (n:Category {node_id: 'PPA'}) SET n += {name: 'PPA'};
MERGE (n:Category {node_id: 'Interface'}) SET n += {name: 'Interface'};
MERGE (n:Category {node_id: 'Design'}) SET n += {name: 'Design'};

// ---- Component nodes (10) ----
MERGE (n:Component {node_id: 'CVA6'}) SET n += {name: 'CVA6', full_name: 'CORE-V Application class processor 6-stage', optional: false};
MERGE (n:Component {node_id: 'CV64A6'}) SET n += {name: 'CV64A6', full_name: 'CVA6 64-bit configuration', optional: false};
MERGE (n:Component {node_id: 'CV32A6'}) SET n += {name: 'CV32A6', full_name: 'CVA6 32-bit configuration', optional: false};
MERGE (n:Component {node_id: 'CSR'}) SET n += {name: 'CSR', full_name: 'Control and Status Register', optional: false};
MERGE (n:Component {node_id: 'PMP'}) SET n += {name: 'PMP', full_name: 'Physical Memory Protection', optional: true};
MERGE (n:Component {node_id: 'TLB'}) SET n += {name: 'TLB', full_name: 'Translation Lookaside Buffer', optional: false};
MERGE (n:Component {node_id: 'L1WTD'}) SET n += {name: 'L1WTD', full_name: 'L1 write-through data cache', optional: false};
MERGE (n:Component {node_id: 'L1I'}) SET n += {name: 'L1I', full_name: 'L1 instruction cache', optional: false};
MERGE (n:Component {node_id: 'CLINT'}) SET n += {name: 'CLINT', full_name: 'Core-Local Interruptor', optional: true};
MERGE (n:Component {node_id: 'TRI'}) SET n += {name: 'TRI', full_name: 'Transaction-Response Interface', optional: false};

// ---- Standard nodes (13) ----
MERGE (n:Standard {node_id: 'RVunpriv'}) SET n += {name: 'RVunpriv', description: 'RISC-V User-Level ISA'};
MERGE (n:Standard {node_id: 'RVcompat'}) SET n += {name: 'RVcompat', description: 'RISC-V Architectural Compatibility Test'};
MERGE (n:Standard {node_id: 'RVpriv'}) SET n += {name: 'RVpriv', description: 'RISC-V Privileged Architecture'};
MERGE (n:Standard {node_id: 'RVdbg'}) SET n += {name: 'RVdbg', description: 'RISC-V External Debug Support'};
MERGE (n:Standard {node_id: 'RV64I'}) SET n += {name: 'RV64I', description: 'RISC-V 64-bit base ISA'};
MERGE (n:Standard {node_id: 'RV32I'}) SET n += {name: 'RV32I', description: 'RISC-V 32-bit base ISA'};
MERGE (n:Standard {node_id: 'Sv39'}) SET n += {name: 'Sv39', description: 'RISC-V Sv39 virtual memory'};
MERGE (n:Standard {node_id: 'Sv32'}) SET n += {name: 'Sv32', description: 'RISC-V Sv32 virtual memory'};
MERGE (n:Standard {node_id: 'OpenPiton'}) SET n += {name: 'OpenPiton', description: 'OpenPiton coherence system'};
MERGE (n:Standard {node_id: 'FENCE.T'}) SET n += {name: 'FENCE.T', description: 'Fence-T custom instruction'};
MERGE (n:Standard {node_id: 'AXI5'}) SET n += {name: 'AXI5', description: 'AXI5 Specification'};
MERGE (n:Standard {node_id: 'AXI'}) SET n += {name: 'AXI', description: 'AXI Specification'};
MERGE (n:Standard {node_id: 'CV-X-IF'}) SET n += {name: 'CV-X-IF', description: 'Core-V eXtension interface'};

// ---- Configuration nodes (2) ----
MERGE (n:Configuration {node_id: 'cv32a6_imac_sv32'}) SET n += {name: 'cv32a6_imac_sv32', description: 'CVA6 32-bit IMAC ISA with Sv32'};
MERGE (n:Configuration {node_id: 'cv64a6_imacfd_sv39'}) SET n += {name: 'cv64a6_imacfd_sv39', description: 'CVA6 64-bit IMACFD ISA with Sv39'};

// ---- Smell nodes (9) ----
MERGE (n:Smell {node_id: 'smell_1'}) SET n += {smell_type: 'vagueness', trigger: 'some', severity: 'high', position: 0, explanation: '\'some\' is an imprecise quantifier. Specify exact quantities or ranges.'};
MERGE (n:Smell {node_id: 'smell_2'}) SET n += {smell_type: 'implicit_reference', trigger: 'it', severity: 'low', position: 0, explanation: 'The pronoun \'it\' may refer to multiple entities. Use explicit nouns to avoid ambiguity.'};
MERGE (n:Smell {node_id: 'smell_3'}) SET n += {smell_type: 'implicit_reference', trigger: 'this', severity: 'low', position: 87, explanation: 'The pronoun \'this\' may refer to multiple entities. Use explicit nouns to avoid ambiguity.'};
MERGE (n:Smell {node_id: 'smell_4'}) SET n += {smell_type: 'implicit_reference', trigger: 'it', severity: 'low', position: 0, explanation: 'The pronoun \'it\' may refer to multiple entities. Use explicit nouns to avoid ambiguity.'};
MERGE (n:Smell {node_id: 'smell_5'}) SET n += {smell_type: 'implicit_reference', trigger: 'this', severity: 'low', position: 85, explanation: 'The pronoun \'this\' may refer to multiple entities. Use explicit nouns to avoid ambiguity.'};
MERGE (n:Smell {node_id: 'smell_6'}) SET n += {smell_type: 'missing_unit', trigger: '7', severity: 'low', position: 87, explanation: 'The numeric value \'7\' may be missing a measurement unit. Verify that the unit is clear from context.'};
MERGE (n:Smell {node_id: 'smell_7'}) SET n += {smell_type: 'missing_unit', trigger: '2', severity: 'low', position: 118, explanation: 'The numeric value \'2\' may be missing a measurement unit. Verify that the unit is clear from context.'};
MERGE (n:Smell {node_id: 'smell_8'}) SET n += {smell_type: 'placeholder', trigger: 'TBD', severity: 'high', position: 0, explanation: 'The marker \'TBD\' indicates incomplete content. The requirement must be filled in before it can be considered finalized.'};
MERGE (n:Smell {node_id: 'smell_9'}) SET n += {smell_type: 'placeholder', trigger: 'TBD', severity: 'high', position: 0, explanation: 'The marker \'TBD\' indicates incomplete content. The requirement must be filled in before it can be considered finalized.'};

// ---- BELONGS_TO relationships (64) ----
MATCH (a:Requirement {node_id: 'GEN-10'}), (b:Category {node_id: 'General'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'ISA-10'}), (b:Category {node_id: 'ISA'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'ISA-20'}), (b:Category {node_id: 'ISA'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'ISA-30'}), (b:Category {node_id: 'ISA'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'ISA-40'}), (b:Category {node_id: 'ISA'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'ISA-50'}), (b:Category {node_id: 'ISA'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'ISA-60'}), (b:Category {node_id: 'ISA'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'ISA-70'}), (b:Category {node_id: 'ISA'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'ISA-80'}), (b:Category {node_id: 'ISA'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'ISA-90'}), (b:Category {node_id: 'ISA'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'ISA-100'}), (b:Category {node_id: 'ISA'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'ISA-120'}), (b:Category {node_id: 'ISA'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'ISA-130'}), (b:Category {node_id: 'ISA'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'ISA-140'}), (b:Category {node_id: 'ISA'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'ISA-150'}), (b:Category {node_id: 'ISA'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'PVL-10'}), (b:Category {node_id: 'Privileges'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'PVL-20'}), (b:Category {node_id: 'Privileges'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'PVL-30'}), (b:Category {node_id: 'Privileges'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'PVL-40'}), (b:Category {node_id: 'Privileges'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'PVL-50'}), (b:Category {node_id: 'Privileges'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'PVL-60'}), (b:Category {node_id: 'Privileges'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'HPM-10'}), (b:Category {node_id: 'Performance'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'HPM-20'}), (b:Category {node_id: 'Performance'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'HPM-30'}), (b:Category {node_id: 'Performance'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'HPM-40'}), (b:Category {node_id: 'Performance'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'HPM-50'}), (b:Category {node_id: 'Performance'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'HPM-60'}), (b:Category {node_id: 'Performance'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'HPM-70'}), (b:Category {node_id: 'Performance'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'HPM-80'}), (b:Category {node_id: 'Performance'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'L1W-10'}), (b:Category {node_id: 'Cache'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'L1W-20'}), (b:Category {node_id: 'Cache'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'L1W-30'}), (b:Category {node_id: 'Cache'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'L1W-40'}), (b:Category {node_id: 'Cache'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'L1W-50'}), (b:Category {node_id: 'Cache'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'L1W-60'}), (b:Category {node_id: 'Cache'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'L1W-70'}), (b:Category {node_id: 'Cache'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'L1W-80'}), (b:Category {node_id: 'Cache'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'L1W-90'}), (b:Category {node_id: 'Cache'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'L1W-100'}), (b:Category {node_id: 'Cache'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'L1I-10'}), (b:Category {node_id: 'Cache'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'L1I-20'}), (b:Category {node_id: 'Cache'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'L1I-30'}), (b:Category {node_id: 'Cache'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'L1I-40'}), (b:Category {node_id: 'Cache'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'L1I-50'}), (b:Category {node_id: 'Cache'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'L1I-60'}), (b:Category {node_id: 'Cache'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'L1I-70'}), (b:Category {node_id: 'Cache'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'FET-10'}), (b:Category {node_id: 'Instruction'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'FET-20'}), (b:Category {node_id: 'Instruction'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'PPA-10'}), (b:Category {node_id: 'PPA'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'PPA-20'}), (b:Category {node_id: 'PPA'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'PPA-30'}), (b:Category {node_id: 'PPA'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'PPA-40'}), (b:Category {node_id: 'PPA'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'PPA-50'}), (b:Category {node_id: 'PPA'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'PPA-60'}), (b:Category {node_id: 'PPA'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'MEM-10'}), (b:Category {node_id: 'Interface'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'MEM-20'}), (b:Category {node_id: 'Interface'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'DBG-10'}), (b:Category {node_id: 'Interface'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'IRQ-10'}), (b:Category {node_id: 'Interface'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'XIF-10'}), (b:Category {node_id: 'Interface'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'TRI-10'}), (b:Category {node_id: 'Interface'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'RUL-10'}), (b:Category {node_id: 'Design'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'RUL-20'}), (b:Category {node_id: 'Design'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'RUL-30'}), (b:Category {node_id: 'Design'}) MERGE (a)-[:BELONGS_TO]->(b);
MATCH (a:Requirement {node_id: 'RUL-40'}), (b:Category {node_id: 'Design'}) MERGE (a)-[:BELONGS_TO]->(b);

// ---- MENTIONS relationships (75) ----
MATCH (a:Requirement {node_id: 'GEN-10'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'ISA-10'}), (b:Component {node_id: 'CV64A6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'ISA-20'}), (b:Component {node_id: 'CV32A6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'ISA-30'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'ISA-40'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'ISA-50'}), (b:Component {node_id: 'CV32A6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'ISA-60'}), (b:Component {node_id: 'CV64A6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'ISA-70'}), (b:Component {node_id: 'CV64A6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'ISA-80'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'ISA-90'}), (b:Component {node_id: 'CSR'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'ISA-90'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'ISA-100'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'ISA-120'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'ISA-130'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'ISA-140'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'ISA-150'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'PVL-10'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'PVL-20'}), (b:Component {node_id: 'CV64A6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'PVL-30'}), (b:Component {node_id: 'CV32A6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'PVL-40'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'PVL-50'}), (b:Component {node_id: 'PMP'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'PVL-50'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'PVL-60'}), (b:Component {node_id: 'CV64A6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'HPM-10'}), (b:Component {node_id: 'CV32A6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'HPM-10'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'HPM-20'}), (b:Component {node_id: 'CV32A6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'HPM-20'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'HPM-30'}), (b:Component {node_id: 'TLB'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'HPM-50'}), (b:Component {node_id: 'CSR'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'HPM-50'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'HPM-60'}), (b:Component {node_id: 'CSR'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'HPM-60'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'HPM-70'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'HPM-80'}), (b:Component {node_id: 'CV32A6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'HPM-80'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'L1W-10'}), (b:Component {node_id: 'L1WTD'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'L1W-10'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'L1W-20'}), (b:Component {node_id: 'L1WTD'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'L1W-20'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'L1W-30'}), (b:Component {node_id: 'L1WTD'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'L1W-40'}), (b:Component {node_id: 'L1WTD'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'L1W-50'}), (b:Component {node_id: 'L1WTD'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'L1W-60'}), (b:Component {node_id: 'L1WTD'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'L1W-70'}), (b:Component {node_id: 'L1WTD'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'L1W-80'}), (b:Component {node_id: 'L1WTD'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'L1W-90'}), (b:Component {node_id: 'L1WTD'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'L1W-100'}), (b:Component {node_id: 'CSR'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'L1W-100'}), (b:Component {node_id: 'L1WTD'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'L1I-10'}), (b:Component {node_id: 'L1I'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'L1I-20'}), (b:Component {node_id: 'L1I'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'L1I-30'}), (b:Component {node_id: 'L1I'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'L1I-40'}), (b:Component {node_id: 'L1I'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'L1I-50'}), (b:Component {node_id: 'L1I'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'L1I-60'}), (b:Component {node_id: 'L1I'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'L1I-70'}), (b:Component {node_id: 'L1I'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'L1I-70'}), (b:Component {node_id: 'CSR'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'FET-10'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'PPA-10'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'PPA-20'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'PPA-30'}), (b:Component {node_id: 'CV32A6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'PPA-40'}), (b:Component {node_id: 'CV64A6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'MEM-10'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'MEM-20'}), (b:Component {node_id: 'L1I'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'MEM-20'}), (b:Component {node_id: 'L1WTD'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'MEM-20'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'DBG-10'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'IRQ-10'}), (b:Component {node_id: 'CLINT'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'IRQ-10'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'XIF-10'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'TRI-10'}), (b:Component {node_id: 'TRI'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'TRI-10'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'RUL-10'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'RUL-20'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'RUL-30'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);
MATCH (a:Requirement {node_id: 'RUL-40'}), (b:Component {node_id: 'CVA6'}) MERGE (a)-[:MENTIONS]->(b);

// ---- REFERS_TO relationships (21) ----
MATCH (a:Requirement {node_id: 'GEN-10'}), (b:Standard {node_id: 'RVunpriv'}) MERGE (a)-[:REFERS_TO]->(b);
MATCH (a:Requirement {node_id: 'GEN-10'}), (b:Standard {node_id: 'RVcompat'}) MERGE (a)-[:REFERS_TO]->(b);
MATCH (a:Requirement {node_id: 'GEN-10'}), (b:Standard {node_id: 'RVpriv'}) MERGE (a)-[:REFERS_TO]->(b);
MATCH (a:Requirement {node_id: 'GEN-10'}), (b:Standard {node_id: 'RVdbg'}) MERGE (a)-[:REFERS_TO]->(b);
MATCH (a:Requirement {node_id: 'ISA-10'}), (b:Standard {node_id: 'RV64I'}) MERGE (a)-[:REFERS_TO]->(b);
MATCH (a:Requirement {node_id: 'ISA-20'}), (b:Standard {node_id: 'RV32I'}) MERGE (a)-[:REFERS_TO]->(b);
MATCH (a:Requirement {node_id: 'PVL-20'}), (b:Standard {node_id: 'Sv39'}) MERGE (a)-[:REFERS_TO]->(b);
MATCH (a:Requirement {node_id: 'PVL-30'}), (b:Standard {node_id: 'Sv32'}) MERGE (a)-[:REFERS_TO]->(b);
MATCH (a:Requirement {node_id: 'HPM-10'}), (b:Standard {node_id: 'RVpriv'}) MERGE (a)-[:REFERS_TO]->(b);
MATCH (a:Requirement {node_id: 'L1W-50'}), (b:Standard {node_id: 'OpenPiton'}) MERGE (a)-[:REFERS_TO]->(b);
MATCH (a:Requirement {node_id: 'L1W-70'}), (b:Standard {node_id: 'FENCE.T'}) MERGE (a)-[:REFERS_TO]->(b);
MATCH (a:Requirement {node_id: 'L1I-30'}), (b:Standard {node_id: 'OpenPiton'}) MERGE (a)-[:REFERS_TO]->(b);
MATCH (a:Requirement {node_id: 'L1I-40'}), (b:Standard {node_id: 'FENCE.T'}) MERGE (a)-[:REFERS_TO]->(b);
MATCH (a:Requirement {node_id: 'FET-10'}), (b:Standard {node_id: 'FENCE.T'}) MERGE (a)-[:REFERS_TO]->(b);
MATCH (a:Requirement {node_id: 'FET-20'}), (b:Standard {node_id: 'FENCE.T'}) MERGE (a)-[:REFERS_TO]->(b);
MATCH (a:Requirement {node_id: 'MEM-10'}), (b:Standard {node_id: 'AXI5'}) MERGE (a)-[:REFERS_TO]->(b);
MATCH (a:Requirement {node_id: 'MEM-10'}), (b:Standard {node_id: 'AXI'}) MERGE (a)-[:REFERS_TO]->(b);
MATCH (a:Requirement {node_id: 'MEM-20'}), (b:Standard {node_id: 'AXI'}) MERGE (a)-[:REFERS_TO]->(b);
MATCH (a:Requirement {node_id: 'DBG-10'}), (b:Standard {node_id: 'RVdbg'}) MERGE (a)-[:REFERS_TO]->(b);
MATCH (a:Requirement {node_id: 'XIF-10'}), (b:Standard {node_id: 'CV-X-IF'}) MERGE (a)-[:REFERS_TO]->(b);
MATCH (a:Requirement {node_id: 'TRI-10'}), (b:Standard {node_id: 'OpenPiton'}) MERGE (a)-[:REFERS_TO]->(b);

// ---- APPLIES_TO relationships (2) ----
MATCH (a:Requirement {node_id: 'PPA-30'}), (b:Configuration {node_id: 'cv32a6_imac_sv32'}) MERGE (a)-[:APPLIES_TO]->(b);
MATCH (a:Requirement {node_id: 'PPA-40'}), (b:Configuration {node_id: 'cv64a6_imacfd_sv39'}) MERGE (a)-[:APPLIES_TO]->(b);

// ---- HAS_SMELL relationships (9) ----
MATCH (a:Requirement {node_id: 'L1W-60'}), (b:Smell {node_id: 'smell_1'}) MERGE (a)-[:HAS_SMELL]->(b);
MATCH (a:Requirement {node_id: 'L1W-70'}), (b:Smell {node_id: 'smell_2'}) MERGE (a)-[:HAS_SMELL]->(b);
MATCH (a:Requirement {node_id: 'L1W-90'}), (b:Smell {node_id: 'smell_3'}) MERGE (a)-[:HAS_SMELL]->(b);
MATCH (a:Requirement {node_id: 'L1I-40'}), (b:Smell {node_id: 'smell_4'}) MERGE (a)-[:HAS_SMELL]->(b);
MATCH (a:Requirement {node_id: 'L1I-60'}), (b:Smell {node_id: 'smell_5'}) MERGE (a)-[:HAS_SMELL]->(b);
MATCH (a:Requirement {node_id: 'PPA-30'}), (b:Smell {node_id: 'smell_6'}) MERGE (a)-[:HAS_SMELL]->(b);
MATCH (a:Requirement {node_id: 'PPA-30'}), (b:Smell {node_id: 'smell_7'}) MERGE (a)-[:HAS_SMELL]->(b);
MATCH (a:Requirement {node_id: 'PPA-50'}), (b:Smell {node_id: 'smell_8'}) MERGE (a)-[:HAS_SMELL]->(b);
MATCH (a:Requirement {node_id: 'PPA-60'}), (b:Smell {node_id: 'smell_9'}) MERGE (a)-[:HAS_SMELL]->(b);
