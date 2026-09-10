# Units: design notes (deferred)

**Status: proposal, not a spec. Nothing here is implemented.** This is a parked design
discussion, kept so the next person to pick it up doesn't re-derive it from scratch. Like
`TODO.md`, it deliberately sits outside the toctree — it documents a decision to *wait*, not a
feature that exists.

**What is actually implemented today** is `stardust.units.UnitConverter` (see below), plus a
handful of ad-hoc unit parsers scattered across dependent projects. That situation is understood
and accepted for now.

---

## 1. What kicked this off

A driver in Constellation (`SiglentSDG2000X`, an arbitrary waveform generator) has to read numeric
values out of SCPI replies that carry unit suffixes:

```
C1:BSWV WVTP,SINE,FRQ,1000HZ,PERI,0.001S,AMP,2.775V,AMPVRMS,0.980963Vrms,OFST,0V,...
```

So `1000HZ` → 1000.0, `2.775V` → 2.775, and — the case that matters — `1.5MHZ` → 1500000.0 and
`50mV` → 0.05. The original driver did this by chopping a fixed number of trailing characters
(`freq_str[:-2]`), which silently turns `1.5MHZ` into `1.5`. That was fixed with a local
prefix table:

```python
_BASE_UNITS = ("HZ", "V", "VRMS", "VPP", "S", "DEG", "%")
_SI_PREFIXES = {"n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9}
```

...which was immediately and correctly criticised for being a **cross product**: 7 prefixes × 7
base units accepts all 49 combinations, including `M%`, `kS`, `kDEG` and `nVRMS`, none of which
are things an instrument can say. It misparses nothing real (no legitimate base unit begins with a
character that is also a prefix, so nothing gets falsely split), but it is laxer than its own
docstring claims to be.

The broader observation, and the reason for this document: **this logic is going to be needed in a
dozen places and across several libraries, and it does not belong in an instrument-category
module.** It belongs in `stardust.units`.

---

## 2. What already exists

### 2.1 `stardust.units`

- `lin_to_dB` / `dB_to_lin` — fine, unrelated to this.
- `UnitDefinition(unit_type, name, to_SI, from_SI, is_SI)` — one unit, with **callables** for
  conversion in each direction and a string `unit_type` grouping related units.
- `make_units()` — a hand-written list of definitions.
- `UnitConverter` — holds that list; `convert(value, from_unit, to_unit)` looks both up by exact
  name, converts to SI and back out. Raises on an unrecognised name.

Three things to know about it before changing anything:

1. **`UnitDefinition.__init__` had a bug — now fixed.** It used to set `self.is_SI = False`
   unconditionally, ignoring the `is_SI` argument, so `V` was not in fact marked as the SI unit.
   Nothing read the attribute, so no caller can have depended on the old behaviour. Note the flag
   is looser than its name: `Vrms` is flagged because it is what `elec-potential-ac` converts
   via, not because volts-RMS is an SI unit. A real design should name this something like
   `is_base_unit`.

2. **Prefixed units are enumerated individually.** `V`, `mV` and `uV` are three separate
   `UnitDefinition` entries. This is the same cross-product problem as the driver's table, one
   layer up: every new base unit needs its prefixes written out by hand, and any prefix nobody
   thought to add simply doesn't exist.

3. **`Vpp ↔ Vrms` hard-codes the sine factor.** `make_units()` defines
   `Vpp = Vrms · 2√2` with a bare `# 1.41... = sqrt(2)` comment. That relationship holds **only
   for a sine wave**. A square wave is 2×, a pulse depends on duty cycle, and noise has no fixed
   relationship at all. This is a live trap: the AWG category that motivated this work has a
   `waveform_type` field sitting directly beside `amplitude`, and its hardware test drives that
   channel through NOISE and DC.

   It is currently defused only by accident — `V` is in unit type `elec-potential-dc` and
   `Vrms`/`Vpp` are in `elec-potential-ac`, so `convert(1, "Vpp", "V")` raises rather than
   returning a wrong answer. Safe, but it also means the AWG cannot express its amplitude in
   volts, which is the actual use case.

   A `WARNING` comment recording the sine-only restriction is now in `make_units()`. The factor
   itself is unchanged — it is correct for the sine case, and there is nowhere to put the waveform
   in the current model.

- `UnitConverter` has six tests in `tests/test_units.py` pinning its behaviour, and is public API
  in a released version. It should be kept working (as a shim, if the internals change) rather
  than broken.

### 2.2 Duplicate prefix tables in dependent code

At the time of writing there are **three** independent copies of SI-prefix logic:

| Where | What it is |
|---|---|
| `stardust.units.make_units()` | `mV`/`uV`/`km` as hand-enumerated `UnitDefinition`s |
| `constellation/.../Siglent_SDG2000X_dvr.py` | `_SI_PREFIXES` + `_BASE_UNITS`, for parsing replies |
| `constellation/ui.py` (`UNIT_PREFIXES`) | `T…f` table for the GUI's unit selector and autoscale |

Consolidating these is most of the practical payoff of doing this work at all.

---

## 3. The proposal

### 3.1 The initiating idea

The original sketch, as proposed:

- Define a **unit class** holding a base unit — `Hz`, `V`, etc.
- Define **globally a set of recognised scientific prefixes**. The unit class carries a flag to
  enable or disable them, enabled by default, so `%` or `S` can opt out.
- Allow a **case-insensitive lookup table** that necessarily loses information but makes the class
  handle `MV` and `UV` correctly — no scope is reporting 200e6 V when it means 200e-3 V. This
  should be **locally overridable**: a high-voltage controller where megavolts are genuinely
  reasonable could disable the default `MV → mV` reading.
- Provide a **parser** in both directions: a string from a unit class, and a unit class from a
  string, so the complex object can be persisted as `"mV"` rather than as a serialised class
  definition.

Open questions raised alongside it:

- Should there be a **parent class for unit categories** — a `power` class that `dBm` and `W` both
  belong to, with `is_SI` and `to_SI`/`from_SI` callables enabling automatic conversion?
- How should this **interact with, integrate into, or replace `UnitConverter`**?
- How should **alternative representations of the same unit** be handled? `Vrms` and `Vpp` both
  describe a sine wave and convert to each other as though they were different units of the same
  idea — but they are more *measurements of a signal* than pure units, the unit really being `V`.

### 3.2 Refinements proposed in response

**(a) The serialization constraint drives everything.** A unit must be reconstructible from its
string form, because units are stored inside serialised state (JSON, HDF5) and, in Constellation's
case, shipped between processes over the network. So the parser is not a convenience feature — it
is the primary interface. **The string is the truth; the unit object is a registry lookup.**

**(b) The unit should be the *base* unit; the prefix is a separate attribute.** `V` is a unit;
`mV` is `(prefix="m", unit=V)`. This is the single change that kills both cross-product problems
at once — the driver's and `make_units()`'s — because illegal combinations stop being something
an allowlist has to exclude and become unrepresentable:

```python
Unit("Hz", dimension=FREQUENCY)                  # prefixes: all, by default
Unit("%",  dimension=DIMENSIONLESS, prefixes=False)
Unit("dBm", dimension=POWER, prefixes=False,     # there is no such thing as a kdBm
     to_SI=..., from_SI=...)
```

Note that the `prefixes` flag is *required for correctness* on logarithmic units, not merely
tidiness: `mdBm` is meaningless, and only the flag can say so.

**(c) Case folding should be a fallback, not the primary path.** Rather than a global
`MV → mV` rule: try an exact-case match first, fold case only if that fails, and **report that a
fold happened**.

```
parse("mV")  → 1e-3 V     exact; no ambiguity, no guess
parse("MV")  → 1e-3 V     folded; result carries something like .assumed = "M→m"
```

An instrument that correctly distinguishes case is then never subjected to the guess, and the
guess only fires for instruments that shout everything in uppercase — which is exactly the
motivating case (`1000HZ`, but `0.980963Vrms`, in the same reply). A recorded `.assumed` lets a
caller log "I read MV as millivolts" rather than deciding silently. The high-voltage override then
becomes per-unit data (`ambiguous_prefix_prefers="M"`) instead of a global switch.

**(d) Unit categories: yes to the concept, no to inheritance.** A grouping is needed — it is the
only thing that can answer "is this conversion legal?" — but it should be **composition**: a
`Unit` *has* a `Dimension`; it is not a subclass of one. Units are constructed from strings at
runtime off instrument replies, so subclassing would mean building classes dynamically at parse
time. This is really just `UnitDefinition.unit_type` promoted from a loose string to a real
object. `to_SI`/`from_SI` as callables was already the right call, because `dBm → W` is not a
scale factor. Callables don't serialise, which is fine — units serialise as strings and the
callables live in the registry.

**(e) `UnitConverter` becomes a thin deprecated shim** over the new registry, keeping
`convert(value, from_unit, to_unit)` and its six tests working. The instance pattern
(`converter = UnitConverter()`) buys nothing once the registry is global.

**(f) `Vrms`/`Vpp`: split the unit from the measurement convention.** The proposal's own framing
made literal — `"Vpp"` parses as `Unit(V)` plus `Convention(pp)`. Both then report
`base_unit == "V"`, so prefix scaling and GUI labelling work uniformly without caring which
convention is in play. Conversions *within* a convention are always safe; conversions *across*
conventions require a waveform and refuse without one:

```python
convert(1.5e6, "Hz", "kHz")                   → 1500.0
convert(2.0, "Vpp", "mV")                     → 2000.0     # same convention, pure prefix
convert(2.0, "Vpp", "Vrms")                   → raises: needs a waveform
convert(2.0, "Vpp", "Vrms", waveform="sine")  → 0.7071
```

`dBm`/`dBV` stay ordinary units rather than conventions: their conversion to W/V is exact and
waveform-independent, so the `to_SI`/`from_SI` model already handles them correctly.

### 3.3 Questions left undecided

These were put and deliberately not answered, because the work was deferred:

1. **`Vrms`/`Vpp` model** — unit+convention (3.2f), versus one dimension with waveform-gated
   conversion (no `Convention` object; simpler, but nothing records which convention a stored
   value used), versus keeping them in separate dimensions as today (safest, but the motivating
   case stays unsolved).
2. **Scope of a first implementation** — the four real call sites (§4), versus parse+convert only,
   versus a full system with quantity arithmetic and compound units (`V/s`, `Hz/V`), which risks
   reinventing pint.
3. **Validation strength** — what a consumer like Constellation's `add_param(unit=...)` should do
   with an unrecognised unit string: warn through the log, pass through silently, or raise. This
   is entangled with a separate cleanup: a majority of existing declarations there use
   non-physical sentinels (`""`, `"1"`, `"bool"`, `"CONST"`), and `""` and `"1"` appear to mean
   the same thing. Any validation has to bless those, so answering this partly means standardising
   them first.

---

## 4. Call sites, when this is picked up

Build for these and nothing else:

1. **Parsing instrument replies** — value+suffix strings into floats in base units.
2. **GUI prefix selector and autoscale** — delete Constellation's `UNIT_PREFIXES`, source the
   table from here.
3. **`convert(values, from_unit, to_unit)`** for data axes — needed by Constellation's planned
   x/y-with-units contract for waveform, trace and spectrum data.
4. **Registry lookup for unit validation** at state-declaration time, including the non-physical
   sentinels above.

---

## 5. Why not pint

[`pint`](https://pint.readthedocs.io/) is the most widely used Python units library. It is not a
dependency of stardust and is not installed; it is recorded here only as a considered and rejected
option.

Its core type is a **`Quantity`**: a number and a unit fused into one object that does arithmetic.

```python
import pint
u = pint.UnitRegistry()

freq = 1.5 * u.MHz
period = (1 / freq).to(u.us)     # 0.6666 microsecond
amp = 2.0 * u.volt
amp + freq                       # DimensionalityError - caught, not silently wrong
amp.to(u.mV)                     # 2000.0 millivolt
```

### What it does well

- Prefix handling, parsing and formatting, all free.
- A large built-in unit database — far more than anyone here would hand-write.
- Real dimensional analysis: adding volts to hertz raises instead of producing a plausible number.
- Arithmetic that carries and combines units through compound expressions.

It would cover most of §3 and do it better than a hand-rolled version.

### What it lacks for these needs

**It doesn't serialise, and that is disqualifying here.** A `Quantity` is an ordinary Python
object holding a reference to the `UnitRegistry` that created it:

- `json.dumps(2.0 * u.volt)` → `TypeError: Object of type Quantity is not JSON serializable`
- `h5py` cannot store it either — it wants arrays and scalars.
- Worse for distributed use, quantities are **bound to their registry instance**; quantities from
  one `UnitRegistry` do not interoperate with another. Any architecture where a value is produced
  in one process and consumed in another hits this directly.

So every serialization boundary would need a manual unwrap to a float plus a unit string, and
every deserialization a re-wrap. At that point the string *is* the storage format and the
`Quantity` is a temporary convenience — a large dependency for a wrapper that cannot be persisted.

**It has no notion of a measurement convention.** `Vpp` is not a unit in pint, and the
waveform-dependent `Vpp ↔ Vrms` relationship (§2.1, §3.2f) has no expression in its model. That
is the one thing this domain most needs and pint least provides.

The design in §3 therefore borrows pint's good idea — a dimension check that makes illegal
conversions raise — while keeping plain floats and unit strings as the storage and wire format.

---

## 6. Decision for now

**Deferred.** No structural changes to `stardust.units`; dependent projects keep their local
tables, including the permissive cross-product ones. The laxness is understood: `kS` and `M%` will
parse, which is wrong but harmless, since no instrument emits them and no legitimate suffix is
misparsed as a result.

Two small items were taken care of independently of the design, since neither depends on it:

- The `is_SI` bug in `UnitDefinition.__init__` is fixed (§2.1). Behaviour change is nil — nothing
  read the attribute.
- `make_units()` now carries a `WARNING` comment that `Vpp ↔ Vrms` is the **sine-only** factor
  (§2.1), so nobody reuses it for a square wave.

Also removed while in there: a stray `# 0.7745 = sqrt(0.6)` comment copy-pasted from the `dBu`
line onto the miles conversion, where it meant nothing.
