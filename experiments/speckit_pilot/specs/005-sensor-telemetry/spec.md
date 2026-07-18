# Feature Specification: Sensor Telemetry Ingestion & Threshold Alerts

**Feature Branch**: `005-sensor-telemetry`

**Created**: 2026-07-18

**Status**: Draft

**Input**: User description: "A backend feature that ingests temperature and vibration telemetry from factory floor sensors, stores the readings, lets plant operators define alert thresholds per sensor, and notifies operators when a threshold is exceeded."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ingest and Store Sensor Telemetry (Priority: P1)

Factory floor sensors continuously report temperature and vibration readings. The system accepts these readings, validates them, and stores them so that plant operators can see current and historical values for any sensor.

**Why this priority**: Everything else in this feature (thresholds, alerting) depends on a reliable stream of stored readings. On its own, this already delivers value: operators gain visibility into equipment conditions and a historical record for maintenance analysis.

**Independent Test**: Can be fully tested by submitting temperature and vibration readings for a known sensor and confirming they are stored and retrievable by sensor and time range — no threshold or notification functionality required.

**Acceptance Scenarios**:

1. **Given** a registered sensor, **When** it reports a temperature reading, **Then** the reading is stored with the sensor identifier, reading type, value, and timestamp, and is retrievable by operators.
2. **Given** a registered sensor, **When** it reports a vibration reading, **Then** the reading is stored and retrievable in the same way as temperature readings.
3. **Given** stored readings for a sensor, **When** an operator requests that sensor's readings for a time range, **Then** all readings within the range are returned in chronological order.
4. **Given** an incoming reading with a missing or non-numeric value, **When** the system processes it, **Then** the reading is rejected, the rejection is recorded, and valid readings from other sensors continue to be processed.

---

### User Story 2 - Define Alert Thresholds per Sensor (Priority: P2)

A plant operator configures alert thresholds for individual sensors — for example, an upper temperature limit of 85°C on a motor housing sensor, or a vibration ceiling on a pump bearing sensor — so that the system knows what "abnormal" means for each piece of equipment.

**Why this priority**: Thresholds are the operator's control surface and a prerequisite for alerting. Without them, stored telemetry is only useful for manual review. This story is independently valuable because operators can see configured limits alongside readings even before notifications exist.

**Independent Test**: Can be tested by creating, updating, and removing a threshold for a specific sensor and confirming the configuration is persisted and reflected when viewed — without any live telemetry flowing.

**Acceptance Scenarios**:

1. **Given** a registered sensor, **When** an operator defines an upper and/or lower threshold for one of its reading types, **Then** the threshold is saved and associated with that sensor and reading type.
2. **Given** an existing threshold, **When** an operator updates its limit value, **Then** subsequent readings are evaluated against the new value, not the old one.
3. **Given** an existing threshold, **When** an operator removes it, **Then** no further alerts are generated for that sensor and reading type.
4. **Given** an operator entering a threshold, **When** they submit an invalid configuration (e.g., lower bound greater than upper bound), **Then** the system rejects it with a clear explanation and the previous configuration remains in effect.

---

### User Story 3 - Notify Operators on Threshold Breach (Priority: P3)

When a sensor reading exceeds a configured threshold, the system raises an alert and notifies the plant operators responsible for that area so they can intervene before equipment damage or downtime occurs.

**Why this priority**: This is the pay-off of the feature — turning passive monitoring into active protection. It is prioritized after ingestion and thresholds because it depends on both, but it is the primary reason operators asked for the feature.

**Independent Test**: With ingestion and a configured threshold in place, can be tested by submitting a reading that violates the threshold and confirming an alert is recorded and a notification is delivered to the assigned operators.

**Acceptance Scenarios**:

1. **Given** a sensor with a configured upper threshold, **When** a reading arrives that exceeds the threshold, **Then** an alert is created recording the sensor, reading value, threshold value, and time of breach, and operators are notified.
2. **Given** an ongoing breach (consecutive readings above threshold), **When** additional violating readings arrive, **Then** the system does not send a separate notification for every reading, but treats them as part of the same alert episode.
3. **Given** an active alert, **When** a subsequent reading returns within the threshold, **Then** the alert episode is marked as resolved with the recovery time recorded.
4. **Given** a sensor with no threshold configured, **When** any reading arrives, **Then** no alert is generated regardless of the value.

---

### User Story 4 - Review Alert History (Priority: P4)

An operator or maintenance planner reviews past alerts — which sensors breached, how often, for how long — to spot recurring problems and plan preventive maintenance.

**Why this priority**: Valuable for longer-term maintenance decisions, but not required for the core monitor-and-notify loop to function.

**Independent Test**: Can be tested by generating several alerts and confirming they can be listed and filtered by sensor and time range, with breach and resolution times visible.

**Acceptance Scenarios**:

1. **Given** past alert episodes, **When** an operator requests the alert history for a sensor or time range, **Then** matching alerts are returned with sensor, reading type, peak value, threshold, start time, and resolution time.

---

### Edge Cases

- What happens when a reading arrives for an unknown (unregistered) sensor identifier? The reading must not be silently dropped — it is recorded as rejected for later investigation.
- How does the system handle readings that oscillate rapidly around a threshold (flapping)? Notifications must not flood operators; the alert episode/deduplication behavior (FR-011) governs this.
- What happens when a sensor stops reporting entirely? Silence is not a threshold breach; detecting stale sensors is noted as out of scope for this feature (see Assumptions).
- How does the system behave when readings arrive out of order or duplicated (e.g., after a sensor gateway reconnects)? Storage must tolerate late and duplicate readings without corrupting history or re-triggering resolved alerts.
- What happens when a threshold is changed while an alert episode is active? The episode is evaluated against the threshold in effect at each reading; changing the threshold so the current value is in range resolves the episode.
- What happens if notification delivery fails? The alert record must still exist and the delivery failure must be recorded so it can be retried or audited.
- What happens during a burst of readings (many sensors reporting simultaneously)? Ingestion must not lose valid readings under expected peak load (see SC-004).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept temperature and vibration telemetry readings reported by registered factory floor sensors.
- **FR-002**: System MUST record for each reading: the sensor identifier, reading type (temperature or vibration), measured value with unit, and the time of measurement.
- **FR-003**: System MUST validate incoming readings and reject those that are malformed (missing fields, non-numeric values, unknown reading type), recording each rejection with a reason without interrupting ingestion of other readings.
- **FR-004**: System MUST record readings received for unregistered sensor identifiers as rejected, retaining enough detail for later investigation, and MUST NOT store them as normal telemetry.
- **FR-005**: System MUST persist accepted readings and allow operators to retrieve them by sensor and time range.
- **FR-006**: System MUST retain stored readings for at least 12 months.
- **FR-007**: Operators MUST be able to define an alert threshold per sensor and per reading type, consisting of an upper limit, a lower limit, or both.
- **FR-008**: Operators MUST be able to view, update, and remove existing thresholds; changes MUST take effect for readings received after the change.
- **FR-009**: System MUST evaluate every accepted reading against the active threshold for its sensor and reading type, and create an alert when the value falls outside the configured limits.
- **FR-010**: System MUST notify the responsible operators when a new alert episode begins, including the sensor, reading type, measured value, violated threshold, and time of breach.
- **FR-011**: System MUST group consecutive violating readings from the same sensor and reading type into a single alert episode and MUST NOT send a separate notification for each violating reading within an episode.
- **FR-012**: System MUST mark an alert episode as resolved when a subsequent reading for that sensor and reading type returns within the threshold, recording the resolution time.
- **FR-013**: System MUST record the delivery outcome of each notification so that failed deliveries are visible and auditable.
- **FR-014**: Operators MUST be able to view alert history, filterable by sensor and time range, including breach start, peak value, threshold in effect, and resolution time.

### Key Entities

- **Sensor**: A registered physical measurement device on the factory floor; identified uniquely, associated with a location/equipment description and the reading types it produces (temperature, vibration).
- **Reading**: A single telemetry measurement; belongs to one sensor, has a reading type, numeric value with unit, measurement timestamp, and ingestion timestamp.
- **Alert Threshold**: An operator-defined limit for one sensor and one reading type; has an optional upper bound and optional lower bound (at least one required), and records who configured it and when.
- **Alert Episode**: A period during which a sensor's readings violate its threshold; references the sensor, reading type, threshold in effect, start time, peak value, and resolution time (open until resolved).
- **Notification**: A message sent to operators for an alert episode; records recipients, send time, and delivery outcome.
- **Operator**: A plant staff member who configures thresholds and receives notifications.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reading reported by a sensor is visible to operators within 10 seconds of being received.
- **SC-002**: Operators are notified within 60 seconds of a threshold-violating reading being received.
- **SC-003**: An operator can configure a new threshold for a sensor in under 2 minutes.
- **SC-004**: The system ingests sustained telemetry from 1,000 sensors reporting every 10 seconds (≈6,000 readings/minute) with zero loss of valid readings.
- **SC-005**: During a continuous breach, operators receive exactly one notification per alert episode rather than one per violating reading.
- **SC-006**: 100% of rejected readings (malformed or unknown sensor) are traceable in rejection records — no telemetry is silently discarded.

## Assumptions

- Sensors are already provisioned and registered in the system by a separate administrative process; sensor onboarding, calibration, and firmware management are out of scope for this feature.
- Sensors (or their gateways) push readings to the system over the plant network; the system does not poll devices.
- Notifications are delivered via the operators' existing channels — assumed to be an in-application alert plus email; per-operator channel preferences (e.g., SMS) can be added later without changing alerting behavior.
- Which operators receive a given sensor's notifications is determined by an existing plant area/role assignment; building a subscription-management UI is out of scope.
- A 12-month reading retention period is assumed as an industry-reasonable default for maintenance analysis; longer archival is out of scope.
- Thresholds are static upper/lower bounds on individual readings; rate-of-change rules, moving averages, and anomaly detection are out of scope for this version.
- Detecting sensors that have gone silent (stale/offline detection) is out of scope for this feature and expected to be addressed separately.
- Expected scale is a single plant with up to roughly 1,000 sensors reporting at intervals of 10 seconds or slower; multi-site deployment is out of scope for v1.
- Operator authentication and authorization reuse the plant's existing user management; all operators with access may configure thresholds (no per-sensor permission model in v1).
