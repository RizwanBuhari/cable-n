import { Link } from 'react-router-dom'
import { WithRail } from '../components/Ads'
import { Icon } from '../components/icons'
import { PageHeader } from '../components/ui'

export default function ResourcesPage() {
  return (
    <WithRail>
      <PageHeader icon={Icon.book} title="Engineering resources" hint="How Cable-N calculates, what each symbol means, and where the methods stop." />
      <article className="prose">
        <h2>1. Single feeder and batch sizing (Modes 1 and 2)</h2>
        <h3>Design current</h3>
        <p>From current directly, or from power: <code>Ib = P / (√3 · V · cos φ)</code> for kW/MW three-phase, <code>Ib = S / (√3 · V)</code> for kVA/MVA (√3 omitted for single-phase, where V is the phase voltage). Power factor is only a divisor for real power, so kW/MW loads require cos φ &gt; 0.</p>
        <h3>Derated current rating</h3>
        <p><code>Iz = Ibase × Ca × Cs × Cd × Cg × runs</code>. The base rating comes from 90 °C XLPE tables for the selected construction and arrangement.</p>
        <ul>
          <li><b>Ca — ambient factor</b>: <code>√((θmax − θamb)/(θmax − θref))</code>, θref = 20 °C in ground, 30 °C in air. For PVC, θmax = 70 °C and an extra ×0.90 construction factor is applied (an approximation of the original program — check against PVC tables).</li>
          <li><b>Cs — soil / duct thermal resistivity factor</b>: tabulated per size; nearest tabled resistivity (0.7–3.0 K·m/W), no interpolation.</li>
          <li><b>Cd — depth factor</b>: tabulated; nearest tabled depth (0.5–3.0 m).</li>
          <li><b>Cg — grouping factor</b>: for parallel runs, from the number of groups and their spacing (touching, 200–800 mm).</li>
        </ul>
        <h3>Voltage drop</h3>
        <p><code>ΔU% = k · I · L · (R cos φ + X sin φ) / V × 100</code>, with k = √3 (three-phase) or 2 (single-phase), and R, X from the engine's per-km tables at the nearest size.</p>
        <h3>Short-circuit withstand</h3>
        <p>Adiabatic: <code>I = k · S / √t</code> (IEC 60364-5-54), k = 143 Cu / 94 Al for XLPE (115 / 76 for PVC). For parallel runs you choose equal sharing (fault ÷ runs) or the full fault per cable.</p>
        <h3>Selection</h3>
        <p>The recommended size is the smallest that passes ampacity, voltage drop and (if requested) the short-circuit check. The <i>governing constraint</i> is the check with the tightest margin. “Recommended” means technically feasible and smallest — not cheapest.</p>

        <h2>2. Current-rating verification (Mode 3)</h2>
        <p>Each duct or position in up to three banks is rated as <code>Ibase × Ca × Cs × Cd × Cg × Cint</code>. Each 2-D bank is treated as a horizontal group of its circuit count at the duct pitch; vertical mutual heating enters only through the depth factor; adjacent banks add an inter-bank factor. This is a table method — a full IEC 60287 study is needed for guaranteed ratings.</p>

        <h2>3. IEC 60287 / 60949 analysis (Mode 4)</h2>
        <p>Rating from the IEC 60287-1-1 heat balance:</p>
        <p><code>I = √[(Δθ − Wd (T1/2 + n(T2 + T3 + T4))) / (R T1 + n R (1 + λ1) T2 + n R (1 + λ1 + λ2)(T3 + T4))]</code></p>
        <p>with mutual heating computed explicitly from every neighbour's actual losses by the image method, iterated to convergence. Electrical parameters, sequence impedances, induced sheath voltage, IEC 60949 short-circuit withstand of conductor and metallic layers, and IEC 60853-2 emergency transients are computed per cable at its own rating.</p>
        <dl className="glossary">
          <dt>T1</dt><dd>Thermal resistance of the insulation, conductor to sheath (K·m/W).</dd>
          <dt>T2</dt><dd>Between sheath and armour: bedding, or the filler of a screened three-core cable (via the Fig. 6 geometric factor G).</dd>
          <dt>T3</dt><dd>Outer covering (jacket).</dd>
          <dt>T4</dt><dd>External: soil (with images), duct air gap + duct wall + surrounding medium, or air with the heat-dissipation coefficient h.</dd>
          <dt>R</dt><dd>AC conductor resistance at maximum temperature, including skin (ks) and proximity (kp) effects.</dd>
          <dt>λ1, λ2</dt><dd>Sheath/screen and armour losses as fractions of conductor loss — large for both-ends bonding.</dd>
          <dt>Wd</dt><dd>Dielectric loss per phase, ∝ U0² · ε · tan δ; significant at HV.</dd>
          <dt>Δθ, ΔT int</dt><dd>Permissible rise above ambient; rise caused by neighbouring cables.</dd>
          <dt>Z1, Z0</dt><dd>Positive- and zero-sequence impedance per km.</dd>
        </dl>

        <h2>4. Limits you should know</h2>
        <ul>
          <li>Table lookups use the nearest tabled value — inputs outside a table range are flagged, never extrapolated.</li>
          <li>Multi-bank Mode 4 results are not validated against CYMCAP and are labelled as estimates.</li>
          <li>Screened three-core λ2 runs low against some CIGRE-guidance studies; effective soil resistivity is the main remaining uncertainty.</li>
          <li>See the <Link to="/validation">Validation centre</Link> for every benchmark, including those outside tolerance, and the <Link to="/disclaimer">engineering disclaimer</Link>.</li>
        </ul>

        <h2>5. Standards referenced</h2>
        <p>IEC 60287-1-1, IEC 60287-2-1, IEC 60949, IEC 60853-2, IEC 60228, IEC 60502, IEC 60364-5-54. Cable-N does not claim compliance with any standard; it implements calculation methods described in them.</p>
      </article>
    </WithRail>
  )
}
