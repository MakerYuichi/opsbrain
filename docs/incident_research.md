# Incident Research Note
## ET AI Hackathon 2.0 — Problem Statement #8

---

## Incident 1 — LG Polymers Vizag Styrene Gas Leak (7 May 2020)

### What happened
At approximately 02:30 AM on 7 May 2020, a cloud of styrene monomer vapour
escaped from Tank M-11 at the LG Polymers India plant in RR Venkatapuram village,
Visakhapatnam. The leak continued for several hours, spreading across a ~3 km
radius. 12 people died, 1,000+ were hospitalised, and ~5,000 residents were
evacuated.

### Causal Chain (verified from public investigations)

| # | Step | Detail |
|---|------|--------|
| 1 | **Shutdown without protocol** | Plant had been closed since 24 March 2020 due to COVID-19 lockdown. Standard shutdown procedure for styrene tanks (circulating chilled brine, dosing inhibitor TBC) was not fully followed. |
| 2 | **Inhibitor depletion** | Tertiary Butyl Catechol (TBC) — the auto-polymerisation inhibitor — was present at inadequate concentration. TBC requires dissolved oxygen to work; stagnant, non-circulated tank allows oxygen stratification. |
| 3 | **Temperature rise** | Ambient temperatures in Vizag reached 38–40°C during April–May. Without chiller circulation, Tank M-11 temperature climbed steadily. TBC is ineffective above ~52°C. |
| 4 | **No temperature sensors** | NGT-appointed committee found the storage tanks were outdated and lacked automated temperature monitoring or alarms. Operators had no real-time visibility. |
| 5 | **Auto-polymerisation onset** | Styrene began exothermic auto-polymerisation (runaway reaction). Heat of reaction further raised tank temperature — a self-accelerating loop. |
| 6 | **Vapour release** | Tank vents opened; styrene vapour (denser than air) settled into surrounding low-lying residential areas. |
| 7 | **No hazard-zone buffer** | Plant operated without valid environmental clearance and the surrounding 500 m was densely populated — warnings went unheeded at community level. |

### Pre-existing signals that were missed
- No maintenance log entries for inhibitor top-up between March 24 and May 7
- No evidence of cooling system inspection before/after lockdown commencement
- Prior DISH/PESO audit had flagged temperature monitoring deficiencies (not acted upon)
- Night-shift guard reportedly noted "pungent smell" ~01:45 AM — no alarm raised

### Sources
- Reuters, May 15 2020 — cooling system likely cause
- Indian Express, May 31 2020 — NGT panel lapses report
- Times of India, May 11 2020 — APFSL forensic report (human error / inhibitor)
- BBC, July 8 2020 — CEO held, outdated tanks finding
- AP News — committee findings on missing temperature sensors

---

## Incident 2 — Vizag Steel Plant (RINL) SMS-1 Ladle Explosion (June 2025)

> Note: Initial reports dated this to "Monday" in what search results indicate is
> around 5–6 June 2025 (publishedDate timestamps ≈ 1780935000). Some sources
> say "January 2025" in problem statement; public record places it in June 2025.
> The fictionalized documents use a composite timeline for the demo.

### What happened
At approximately 4:15–4:40 PM, a ladle carrying ~150 tonnes of molten steel at
~1,600°C exploded in Steel Melting Shop-1 (SMS-1), Continuous Casting
Department (CCD), Caster-1 of the Rashtriya Ispat Nigam Limited (RINL)
Visakhapatnam Steel Plant. The ladle tipped, spilling liquid metal across the shop
floor. 10 workers were killed (8 confirmed immediately; 2 more died from burns).
22 staff were suspended and a SAIL Bokaro-led expert committee was constituted.

### Causal Chain (verified from public investigations)

| # | Step | Detail |
|---|------|--------|
| 1 | **Suspended argon purging** | Investigators found that argon-gas purging of the molten steel bath in the ladle furnace had not been carried out for approximately three weeks prior to the accident. Purging homogenises temperature and chemistry and expels non-metallic inclusions. |
| 2 | **Residual argon pockets** | Preliminary probe (Times of India) found "residual argon-linked fire bubble" hypothesis: retained gas pockets within the melt, not properly vented. |
| 3 | **Possible low-grade raw material** | A separate inquiry thread (Times of India) suggested low-grade raw material input may have contributed to abnormal gas behaviour in the melt. |
| 4 | **Ladle rotation event** | The full ladle was being "rotated and centred" for casting at Caster-1 when the explosion triggered — mechanical agitation likely disturbed the trapped gas pockets. |
| 5 | **Explosion before slide gate** | Before the slide gate was opened, a high-intensity blast occurred. The ladle tipped; ~150 t of 1,600°C steel poured onto the shop floor. |
| 6 | **Crane failure factor** | At least one source (Indian Express) reported the crane carrying the ladle broke — whether this was cause or consequence of the blast is still under investigation. |
| 7 | **Inadequate safety distance** | Workers on the floor below the casting platform were directly exposed with no blast shielding. |

### Pre-existing signals that were missed
- Argon purging skipped for ~3 weeks — no escalation in maintenance records
- Prior coke oven battery issues at the plant created upstream chemistry variability (raw material quality)
- Inspection records for ladle refractory lining not publicly confirmed as current
- No real-time gas-pocket detection in ladle furnace process

### Connection to coke ovens (problem statement framing)
RINL VSP operates coke oven batteries that supply coke to the blast furnaces,
which in turn produce the hot metal charged into SMS ladles. If coke quality
degrades (e.g., from coke oven battery refractory wear, incorrect coal blend,
or battery pressure irregularities), downstream melt chemistry varies, affecting
gas behaviour in the ladle furnace. A knowledge graph connecting coke oven
maintenance logs → blast furnace hot-metal quality logs → SMS ladle process
records would surface this cross-asset causal chain.

### Sources
- Indian Express, June 2025 — trapped gases, ladle rotation detail
- Times of India — argon fire bubble; low-grade raw material thread
- The Hindu — death toll, SMS-1 CCD Caster-1 detail, ₹4 cr/day loss
- BusinessWorld — NHRC notice; 150 t ladle detail

---

## Pattern Summary for Synthetic Dataset Design

Both incidents share a structural fingerprint useful for the Pattern Breaker feature:

1. **Deferred maintenance** — routine safety-critical task skipped for weeks/months
2. **No cross-asset signal aggregation** — warning in one system (cooling, purging) not linked to risk in another (vapour release, ladle explosion)  
3. **Missing or ignored instrumentation** — no temperature sensor / no gas-pocket detector
4. **Permit/clearance gap** — operating without valid environmental clearance (LGP) or with overdue equipment inspection (RINL)
5. **Shift handover blindness** — night-shift guard noting smell but not triggering alarm (LGP); multi-week purging gap crossing shift boundaries (RINL)

Content rephrased for compliance with licensing restrictions.
