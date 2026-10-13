"""Build a self-contained one-page HTML dashboard from the pipeline outputs.

Pure stdlib: reads the outputs/ CSVs and base64-embeds the PNGs so dashboard.html is fully
portable (no external assets). Every section guards on file existence, so a partial run still
yields a valid page. Recomputes nothing - it only presents existing numbers.

Usage:  python3 -m pkinv.report.dashboard
"""

from pkinv.assets import asset_path
import base64
import csv
import html
import json
import os

from pkinv.paths import ROOT

OUT = asset_path(ROOT, "outputs")


def _csv(name, subdir=""):
    path = asset_path(OUT, subdir, name)
    if not os.path.exists(path):
        return None
    with open(path, newline="") as f:
        return list(csv.reader(f))


def _benchmark_panel():
    """The national benchmark comparison, projected to the nine columns the
    retired narrow twin carried (rc35) so the panel stays readable; the
    protocol columns live in the file itself."""
    rows = _csv("national_benchmark_comparison.csv")
    if not rows:
        return None
    keep = ("source", "engine_category", "scope_detail", "year", "benchmark_Mt_co2e",
            "engine_Mt_co2e", "ratio_engine_over_benchmark", "within_0.5_2.0x", "note")
    idx = [rows[0].index(c) for c in keep]
    return [[r[i] for i in idx] for r in rows]


def _table(rows, bold_last=False):
    if not rows:
        return "<p class='missing'>not generated</p>"
    head, body = rows[0], rows[1:]
    h = "".join("<th>%s</th>" % html.escape(c) for c in head)
    trs = []
    for i, r in enumerate(body):
        cls = " class='tot'" if bold_last and i == len(body) - 1 else ""
        tds = "".join("<td>%s</td>" % html.escape(c) for c in r)
        trs.append("<tr%s>%s</tr>" % (cls, tds))
    return "<table><thead><tr>%s</tr></thead><tbody>%s</tbody></table>" % (h, "".join(trs))


def _img(name, subdir=""):
    path = asset_path(OUT, subdir, name)
    if not os.path.exists(path):
        return "<p class='missing'>not generated (run the relevant phase)</p>"
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return "<img src='data:image/png;base64,%s' alt='%s'/>" % (b64, html.escape(name))


def _grep(md_name, needle):
    path = asset_path(OUT, md_name)
    if not os.path.exists(path):
        return ""
    for line in open(path, encoding="utf-8"):
        if needle in line:
            return line.strip().replace("*", "").replace("`", "")
    return ""


def _headline():
    rows = _csv("national_totals_2024.csv")
    if not rows:
        return "<p class='missing'>run the national inventory first</p>", ""
    tot = next((r for r in rows[1:] if r[0] == "TOTAL"), None)
    if not tot:
        return "<p class='missing'>no TOTAL row</p>", ""
    ar5, ar6, unc = tot[1], tot[2], tot[3]
    sens = _grep("inventory_report.md", "EF1 sensitivity")
    big = ("<div class='big'>%s <span>Mt CO<sub>2</sub>e</span></div>"
           "<div class='sub'>AR5 GWP-100 &middot; &plusmn;%s%% &middot; AR6 %s Mt &middot; "
           "2024, provisional (Tier 2)</div>" % (ar5, unc, ar6))
    return big, ("<p class='note'>%s</p>" % html.escape(sens) if sens else "")


def _cagr():
    rows = _csv("timeseries_1990_2024.csv")
    if not rows:
        return ""
    hdr = rows[0]
    ci = hdr.index("co2e_Mt_AR5")
    tot = {int(r[0]): float(r[ci]) for r in rows[1:] if r[1] == "TOTAL" and r[ci]}
    if not tot:
        return ""
    y0, y1 = min(tot), max(tot)
    cagr = ((tot[y1] / tot[y0]) ** (1.0 / (y1 - y0)) - 1) * 100
    return ("%d: %.0f Mt &rarr; %d: %.0f Mt CO<sub>2</sub>e (CAGR %.1f%%/yr)"
            % (y0, tot[y0], y1, tot[y1], cagr))


def _crt_latest():
    rows = _csv("crt_AFOLU_table.csv")
    if not rows:
        return None
    years = [int(r[0]) for r in rows[1:] if r[0].isdigit()]
    if not years:
        return rows
    latest = max(years)
    return [rows[0]] + [r for r in rows[1:] if r[0] == str(latest)]


def _key_category_panel():
    """Key Category Analysis card (IPCC Approach 1); '' if the phase hasn't run."""
    rows = _csv("key_categories.csv")
    if not rows:
        return ""
    hdr = {name: i for i, name in enumerate(rows[0])}
    key_names = [r[hdr["category"]] for r in rows[1:] if r[hdr["key"]] == "YES"]
    trimmed = [["Category", "Level %", "Key (level)", "Trend %", "Key (trend)", "Key"]]
    for r in rows[1:]:
        trimmed.append([r[hdr["category"]], r[hdr["level_pct"]],
                        "✓" if r[hdr["key_by_level"]] == "YES" else "",
                        r[hdr["trend_pct"]],
                        "✓" if r[hdr["key_by_trend"]] == "YES" else "",
                        "✓" if r[hdr["key"]] == "YES" else ""])
    summary = ("<div class='sub'>%d key categories (95%% cumulative, level or trend): "
               "<strong>%s</strong>. These carry the inventory and are where better data and "
               "Tier-2/3 factors reduce national uncertainty most.</div>"
               % (len(key_names), html.escape(", ".join(key_names))))
    return ("<h2>Key category analysis (IPCC Approach 1)</h2>"
            "<div class='card'>%s%s</div>" % (summary, _table(trimmed)))


def _completeness_panel():
    """Completeness / notation-key summary card; '' if the phase hasn't run."""
    rows = _csv("completeness.csv")
    if not rows:
        return ""
    hdr = {name: i for i, name in enumerate(rows[0])}
    counts = {}
    for r in rows[1:]:
        k = r[hdr["notation_key"]]
        counts[k] = counts.get(k, 0) + 1
    legend = {"E": "estimated", "NE": "not estimated", "NO": "not occurring",
              "IE": "included elsewhere", "NA": "not applicable"}
    summary = ("<div class='sub'>%s</div>"
               % " &middot; ".join("<strong>%s</strong> %s (%d)" % (k, legend.get(k, k), counts[k])
                                   for k in ("E", "NE", "NO", "IE", "NA") if k in counts))
    trimmed = [["Code", "Category", "Gas", "Key"]]
    for r in rows[1:]:
        trimmed.append([r[hdr["code"]], r[hdr["category"]], r[hdr["gas"]], r[hdr["notation_key"]]])
    return ("<h2>Completeness &amp; notation keys (IPCC Vol 1 Ch 8)</h2>"
            "<div class='card'>%s%s</div>" % (summary, _table(trimmed)))


def _nowcast_panel():
    """Live crop-fire nowcast card (returns HTML, or '' if the phase hasn't run)."""
    path = asset_path(OUT, "nowcast", "fire_emissions_card.json")
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        c = json.load(f)
    t = c["totals"]
    last = c["last_24h"]
    big = ("<div class='big'>%.3f <span>Mt CO<sub>2</sub>e</span></div>"
           "<div class='sub'>crop-residue burning, %s&ndash;%s &middot; inventory-constrained "
           "&middot; last 24 h (%s): %d fires, %.4f Mt &middot; ~%.0f t PM<sub>2.5</sub></div>"
           % (t["co2e_constrained_Mt"], c["date_range"][0], c["date_range"][1],
              last["date"], last["n_crop_fires"], last["co2e_Mt"], t["pm25_t"]))
    conf = c["confidence"]
    conf_html = ("<div class='sub'>Confidence &mdash; fire location: <strong>%s</strong> &middot; "
                 "crop attribution: <strong>%s</strong> &middot; residue mass: <strong>%s</strong> "
                 "&middot; FRP capture %.0f%%</div>"
                 % (conf["fire_location"], conf["crop_attribution"], conf["residue_mass"],
                    100.0 * c.get("frp_capture_fraction", 0.0)))
    areas = "".join("<tr><td>%s</td><td>%.4f</td></tr>"
                    % (html.escape(a["name"]), a["co2e_Mt"]) for a in c["top_areas"] if a["co2e_Mt"] > 0)
    areas_tbl = ("<table><thead><tr><th>Top area</th><th>Mt CO<sub>2</sub>e</th></tr></thead>"
                 "<tbody>%s</tbody></table>" % areas)
    narr = "<p class='note'>%s</p>" % html.escape(c["narrative"])
    caveat = "<p class='note'><em>%s</em></p>" % html.escape(c["caveat"])
    return ("<h2>Live crop-fire GHG pulse (near-real-time nowcast)</h2>"
            "<div class='card'>%s%s%s%s%s%s</div>"
            % (big, conf_html, narr, _img("fire_nowcast_map.png", "nowcast"), areas_tbl, caveat))


def _rice_panel():
    """Rice methane pulse card (returns HTML, or '' if the phase hasn't run)."""
    path = asset_path(OUT, "nowcast", "rice_ch4_card.json")
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        c = json.load(f)
    t = c["totals"]
    peak, awd = c["peak_week"], c["mitigation_awd"]
    big = ("<div class='big'>%.2f <span>Mt CO<sub>2</sub>e</span></div>"
           "<div class='sub'>rice cultivation CH<sub>4</sub>, season %s&ndash;%s &middot; "
           "inventory-constrained &middot; peak week %s (%.3f Mt) &middot; driver: %s</div>"
           % (t["co2e_total_Mt"], c["season_range"][0], c["season_range"][1],
              peak["week_start"], peak["co2e_Mt"], html.escape(c["generated_from"])))
    conf = c["confidence"]
    conf_html = ("<div class='sub'>Confidence &mdash; flooded extent: <strong>%s</strong> &middot; "
                 "crop stage: <strong>%s</strong> &middot; flux per area: <strong>%s</strong></div>"
                 % (conf["flooded_extent"], conf["crop_stage"], conf["flux_per_area"]))
    awd_html = ("<div class='sub'>AWD mitigation (SFw %.2f): season CH<sub>4</sub> &rarr; "
                "<strong>%.2f Mt</strong>, avoiding <strong>%.2f Mt CO<sub>2</sub>e</strong></div>"
                % (awd["sfw"], awd["scenario_Mt"], awd["avoided_Mt"]))
    areas = "".join("<tr><td>%s</td><td>%.3f</td></tr>"
                    % (html.escape(a["name"]), a["co2e_Mt"]) for a in c["top_areas"])
    areas_tbl = ("<table><thead><tr><th>Province</th><th>Mt CO<sub>2</sub>e</th></tr></thead>"
                 "<tbody>%s</tbody></table>" % areas)
    narr = "<p class='note'>%s</p>" % html.escape(c["narrative"])
    caveat = "<p class='note'><em>%s</em></p>" % html.escape(c["caveat"])
    return ("<h2>Rice methane pulse (weekly nowcast)</h2>"
            "<div class='card'>%s%s%s%s%s%s%s</div>"
            % (big, conf_html, awd_html, narr, _img("rice_methane_pulse.png", "nowcast"),
               _img("rice_ch4_intensity_map.png", "nowcast"), areas_tbl + caveat))


def _soil_n2o_panel():
    """Soil N2O pulse-risk card (returns HTML, or '' if the phase hasn't run)."""
    path = asset_path(OUT, "nowcast", "soil_n2o_card.json")
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        c = json.load(f)
    t = c["totals"]
    peak, alerts = c["peak_day"], c["pulse_alerts"]
    big = ("<div class='big'>%.2f <span>Mt CO<sub>2</sub>e</span></div>"
           "<div class='sub'>managed-soil N<sub>2</sub>O, %s&ndash;%s &middot; "
           "inventory-constrained &middot; %.1f Mt fertilizer-driven + %.1f Mt background &middot; "
           "peak %s (%.3f Mt) &middot; %d pulse alerts</div>"
           % (t["co2e_total_Mt"], c["date_range"][0], c["date_range"][1],
              t["fertilizer_Mt"], t["background_Mt"], peak["date"], peak["co2e_Mt"],
              alerts["n_alerts"]))
    conf = c["confidence"]
    conf_html = ("<div class='sub'>Confidence &mdash; drivers: <strong>%s</strong> &middot; "
                 "fertilizer timing: <strong>%s</strong> &middot; risk&rarr;flux: <strong>%s</strong>"
                 " &middot; driver: %s</div>"
                 % (conf["environmental_drivers"], conf["fertilizer_timing"],
                    conf["risk_to_flux_mapping"], html.escape(c["generated_from"])))
    ar = "".join("<tr><td>%s</td><td>%s</td><td>%.0f</td><td>%.0f</td></tr>"
                 % (a["date"], html.escape(a["province"]), a["rain_mm"], a["soil_temp_c"])
                 for a in alerts["top"][:6])
    ar_tbl = ("<table><thead><tr><th>Top pulse alert</th><th>Province</th>"
              "<th>Rain mm</th><th>Soil °C</th></tr></thead><tbody>%s</tbody></table>" % ar)
    narr = "<p class='note'>%s</p>" % html.escape(c["narrative"])
    caveat = "<p class='note'><em>%s</em></p>" % html.escape(c["caveat"])
    return ("<h2>Soil N<sub>2</sub>O pulse-risk (daily, risk-informed alert &mdash; "
            "<em>not a flux measurement</em>)</h2>"
            "<div class='card'>%s%s%s%s%s%s</div>"
            % (big, conf_html, narr, _img("soil_n2o_pulse.png", "nowcast"),
               _img("soil_n2o_risk_map.png", "nowcast"), ar_tbl + caveat))


def _livestock_panel():
    """Monthly livestock tracker card (returns HTML, or '' if the phase hasn't run)."""
    path = asset_path(OUT, "nowcast", "livestock_card.json")
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        c = json.load(f)
    t, ms = c["totals"], c["manure_seasonality"]
    big = ("<div class='big'>%.0f <span>Mt CO<sub>2</sub>e</span></div>"
           "<div class='sub'>livestock CH<sub>4</sub>/N<sub>2</sub>O, %s&ndash;%s &middot; "
           "inventory-constrained &middot; enteric %.0f Mt (baseline) + manure %.0f Mt (seasonal) "
           "&middot; manure peaks %s (%.1f× winter)</div>"
           % (t["co2e_total_Mt"], c["month_range"][0], c["month_range"][1],
              t["enteric_Mt"], t["manure_Mt"], ms["peak_month"], ms["peak_over_trough"]))
    conf = c["confidence"]
    conf_html = ("<div class='sub'>Confidence &mdash; population: <strong>%s</strong> &middot; "
                 "manure temperature: <strong>%s</strong> &middot; enteric: <strong>%s</strong> "
                 "&middot; driver: %s</div>"
                 % (conf["population_control"], conf["manure_temperature_response"],
                    conf["enteric_seasonality"], html.escape(c["generated_from"])))
    areas = "".join("<tr><td>%s</td><td>%.1f</td></tr>"
                    % (html.escape(a["name"]), a["co2e_Mt"]) for a in c["top_areas"])
    areas_tbl = ("<table><thead><tr><th>Province</th><th>Mt CO<sub>2</sub>e</th></tr></thead>"
                 "<tbody>%s</tbody></table>" % areas)
    narr = "<p class='note'>%s</p>" % html.escape(c["narrative"])
    caveat = "<p class='note'><em>%s</em></p>" % html.escape(c["caveat"])
    return ("<h2>Livestock CH<sub>4</sub>/N<sub>2</sub>O monthly tracker</h2>"
            "<div class='card'>%s%s%s%s%s%s</div>"
            % (big, conf_html, narr, _img("livestock_monthly.png", "nowcast"),
               _img("livestock_intensity_map.png", "nowcast"), areas_tbl + caveat))


def _land_change_panel():
    """LULUCF land-change alert card (returns HTML, or '' if the phase hasn't run)."""
    path = asset_path(OUT, "nowcast", "land_change_card.json")
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        c = json.load(f)
    fo, m, cc = c["forest"], c["mangrove"], c["cross_check"]
    big = ("<div class='big'>%.2f <span>Mt CO<sub>2</sub>e/yr</span></div>"
           "<div class='sub'>observed forest gross loss (%s&ndash;%s) &middot; cumulative %.0f ha = "
           "%.2f Mt &middot; backbone LULUCF net <strong>%.1f Mt</strong> (unchanged)</div>"
           % (cc["unaccounted_gross_co2e_Mt_yr"], c["forest_year_range"][0],
              c["forest_year_range"][1], fo["cum_loss_ha"], fo["cum_loss_co2e_Mt"],
              c["backbone_net_lulucf_Mt"]))
    mword = "consistent" if cc["mangrove_consistent"] else "DIVERGING"
    xcheck = ("<div class='sub'>Cross-check &mdash; backbone assumes deforestation "
              "<strong>%g ha/yr</strong> vs observed <strong>%.0f</strong>; mangrove assumed "
              "<strong>+%g ha/yr</strong> vs observed <strong>%.0f</strong> (%s)</div>"
              % (cc["backbone_deforestation_ha_yr"], fo["gross_loss_ha_yr"],
                 cc["backbone_mangrove_rate_ha_yr"], cc["observed_mangrove_rate_ha_yr"], mword))
    conf = c["confidence"]
    conf_html = ("<div class='sub'>Confidence &mdash; change detection: <strong>%s</strong> &middot; "
                 "carbon conversion: <strong>%s</strong> &middot; mangrove extent: <strong>%s</strong>"
                 "</div>" % (conf["change_detection"], conf["carbon_conversion"],
                             conf["mangrove_extent"]))
    hs = "".join("<tr><td>%s</td><td>%.0f</td><td>%.4f</td></tr>"
                 % (html.escape(h["province"]), h["loss_ha"], h["co2e_Mt"]) for h in fo["hotspots"])
    hs_tbl = ("<table><thead><tr><th>Forest-loss hotspot</th><th>ha (latest yr)</th>"
              "<th>Mt CO<sub>2</sub>e</th></tr></thead><tbody>%s</tbody></table>" % hs)
    narr = "<p class='note'>%s</p>" % html.escape(c["narrative"])
    caveat = "<p class='note'><em>%s</em></p>" % html.escape(c["caveat"])
    return ("<h2>LULUCF land-change alerts (forest + mangrove, cross-check)</h2>"
            "<div class='card'>%s%s%s%s%s%s%s</div>"
            % (big, xcheck, conf_html, narr, _img("land_change_trend.png", "nowcast"),
               _img("land_change_forest_map.png", "nowcast"), hs_tbl + caveat))


def _district_panel():
    """District (ADM2) downscaling: choropleth + top-emitting districts (HTML or '')."""
    path = asset_path(OUT, "eval", "system_evaluation.json")
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        d = json.load(f).get("district_downscaling")
    if not d:
        return ""
    big = ("<div class='big'>%d <span>districts</span></div>"
           "<div class='sub'>national %.1f Mt CO<sub>2</sub>e dasymetrically split to ADM2; "
           "&Sigma; districts == province control (exact)</div>" % (d["n_districts"], d["national_Mt"]))
    top = _table([["District", "Mt CO<sub>2</sub>e"]]
                 + [[x["district"], "%.2f" % x["Mt"]] for x in d["top_districts"]])
    note = "<p class='note'><em>%s</em></p>" % html.escape(d["note"])
    return ("<h2>District downscaling (ADM2)</h2><div class='card'>%s%s%s%s</div>"
            % (big, _img("district_totals.png", "districts"), top, note))


def _system_eval_panel():
    """Whole-system evaluation panel - empty since rc33 by design.

    The nowcast/ML/backcast evaluation lanes live in the companion research
    repository since the split; their four pkinv.eval modules and the stale
    Aug-5 system_evaluation.json were retired at rc33 (catalog row
    abs-companion-repo-lanes). The graceful-degrade path below keeps the
    dashboard building; the panel returns when the companion repo publishes
    the artifact again."""
    path = asset_path(OUT, "eval", "system_evaluation.json")
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        r = json.load(f)
    st = r["system_totals"]
    big = ("<div class='big'>%.1f <span>Mt CO<sub>2</sub>e AFOLU</span></div>"
           "<div class='sub'>agriculture %.1f + LULUCF %.1f &middot; every reconciling module's "
           "nowcast sums <strong>exactly</strong> to its inventory control</div>"
           % (st["inventory_afolu_Mt"], st["inventory_agriculture_Mt"], st["inventory_lulucf_Mt"]))
    rec = [[x["module"], x["kind"], "%.3f" % x["control_Mt"],
            ("%.3f" % x["nowcast_Mt"]) if x["nowcast_Mt"] is not None else "-",
            x["status"]] for x in r["reconciliation"]]
    rec_tbl = _table([["Module", "Kind", "Control Mt", "Nowcast Mt", "Status"]] + rec)
    sc = [[x["model"], x["metric"], ("%.3f" % x["value"]) if isinstance(x["value"], (int, float)) else "-",
           x.get("independent_validation") or "-"] for x in r["ml_scorecard"]]
    sc_tbl = _table([["ML model", "Metric", "Value", "Independent validation (held-out reference)"]] + sc)
    unc = [[x["module"], "%.2f" % x["annual_mean_Mt"], "%.1f-%.1f" % (x["annual_p5_Mt"], x["annual_p95_Mt"]),
            "%.1f%%" % x["magnitude_rel_pct"], "%.2f%%" % x["distribution_rel_pct"]] for x in r["uncertainty"]]
    unc_tbl = _table([["Module", "Annual Mt", "P5-P95", "Magnitude", "Ensemble"]] + unc)
    note = "<p class='note'><em>%s</em></p>" % html.escape(r["note"])
    return ("<h2>Whole-system evaluation &amp; uncertainty</h2><div class='card'>%s%s"
            "<div class='sub'>Reconciliation rollup</div>%s"
            "<div class='sub'>ML model scorecard</div>%s"
            "<div class='sub'>Uncertainty (magnitude dominates; model ensemble &lt;0.1%%)</div>%s%s%s%s</div>"
            % (big, "", rec_tbl, sc_tbl, unc_tbl, "", note, ""))


def _live_json(name):
    path = asset_path(OUT, "live", name)
    return json.load(open(path)) if os.path.exists(path) else None


def _freshness_panel():
    h = _live_json("source_health.json")
    if not h:
        return ""
    dot = {"green": "#2c9e3f", "yellow": "#d9a300", "red": "#c0392b"}
    rows = "".join(
        "<tr><td><span class='dot' style='background:%s'></span> %s</td><td>%s</td>"
        "<td>%s</td><td>%s d</td></tr>"
        % (dot.get(s["status"], "#999"), html.escape(s["source"]), s["drives"],
           s["latest_data"] or "&mdash;", s["latency_days"] if s["latency_days"] is not None else "&mdash;")
        for s in h["sources"])
    return ("<h2>Source freshness <span style='font-size:11px;color:#667'>(as of %s &middot; overall "
            "<span class='dot' style='background:%s'></span>%s)</span></h2>"
            "<div class='card'><table><tr><th>Source</th><th>Drives</th><th>Latest data</th>"
            "<th>Latency</th></tr>%s</table></div>"
            % (h["as_of"], dot.get(h["overall"], "#999"), h["overall"], rows))


def _alerts_panel():
    a = _live_json("alerts.json")
    if not a:
        return ""
    if not a["alerts"]:
        body = "<p class='sub'>No active alerts as of %s.</p>" % a["as_of"]
    else:
        body = "".join(
            "<div class='alert alert-%s'><strong>%s</strong> &middot; %s &middot; %s "
            "<span class='sub'>(%s, conf %s)</span></div>"
            % (x["severity"], x["module"], html.escape(x["area"]), html.escape(x["message"]),
               x["date"], x["confidence"])
            for x in a["alerts"])
    return ("<h2>Active alerts <span style='font-size:11px;color:#667'>(%d)</span></h2>"
            "<div class='card'>%s</div>" % (a["n_alerts"], body))


def _live_status_panel():
    e = _live_json("rolling_estimate.json")
    if not e:
        return ""
    rows = [["Module", "Mode", "% season", "To-date (Mt)", "±", "Proj. annual"]]
    for m, d in e["modules"].items():
        rows.append([m, d["mode"], "%.0f%%" % d["pct_season_elapsed"],
                     "%.2f" % d["emissions_to_date_live_Mt"], "%.2f" % d["band_Mt"],
                     "%.1f" % d["projected_annual_Mt"]])
    return ("<h2>Live rolling estimate <span style='font-size:11px;color:#667'>(Mode-B, as of %s)"
            "</span></h2><div class='card'>%s<p class='note'><em>%s</em></p></div>"
            % (e["as_of"], _table(rows), html.escape(e["note"])))


def build():
    headline, sens_note = _headline()
    css = """
    body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;
         background:#f5f6f8;color:#1b2430}
    .wrap{max-width:960px;margin:0 auto;padding:24px}
    h1{font-size:22px;margin:0 0 2px} h2{font-size:15px;margin:26px 0 8px;color:#2c5f2d;
       border-bottom:2px solid #2c5f2d;padding-bottom:4px}
    .meta{color:#667;font-size:12px;margin-bottom:18px}
    .card{background:#fff;border-radius:10px;padding:18px 20px;box-shadow:0 1px 3px rgba(0,0,0,.08)}
    .big{font-size:44px;font-weight:700;color:#2c5f2d} .big span{font-size:20px;font-weight:400;color:#445}
    .sub{color:#556;font-size:13px;margin-top:4px} .note{color:#774;font-size:12px;margin-top:8px}
    table{border-collapse:collapse;width:100%;font-size:13px;margin-top:4px}
    th,td{text-align:right;padding:5px 9px;border-bottom:1px solid #e6e8ec}
    th:first-child,td:first-child{text-align:left}
    th{background:#f0f2f4;color:#445;font-weight:600}
    tr.tot{font-weight:700;background:#f7faf7}
    img{max-width:100%;border-radius:8px;border:1px solid #e6e8ec;margin-top:6px}
    .missing{color:#999;font-style:italic;font-size:12px}
    .flags li{font-size:12px;color:#555;margin:3px 0}
    .dot{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:5px;vertical-align:middle}
    .alert{padding:7px 10px;margin:5px 0;border-radius:6px;font-size:13px;border-left:4px solid #999}
    .alert-high{background:#fdecea;border-color:#c0392b} .alert-medium{background:#fff6e5;border-color:#d9a300}
    .alert-low{background:#eef4ff;border-color:#3b73c4}
    .foot{color:#889;font-size:11px;margin-top:28px;text-align:center}
    """
    crt = _crt_latest()
    flags = []
    for needle in ("EF1 = 0.005", "Leaching retained", "Manure-management-system",
                   "divergence from FAOSTAT"):
        line = _grep("inventory_report.md", needle)
        if line:
            flags.append("<li>%s</li>" % html.escape(line.lstrip("- ")))

    parts = ["<!doctype html><html><head><meta charset='utf-8'>",
             "<meta name='viewport' content='width=device-width,initial-scale=1'>",
             "<title>Pakistan Agricultural GHG Dashboard</title><style>%s</style></head><body>" % css,
             "<div class='wrap'>",
             "<h1>Pakistan Ag-GHG Live</h1>",
             "<div class='meta'>Inventory backbone (IPCC Tier 2, 6 categories, 2024) + "
             "live crop-fire nowcast &middot; <strong>provisional</strong> &middot; "
             "generated from pipeline outputs</div>",
             "<div class='card'>%s%s</div>" % (headline, sens_note),

             _live_status_panel(),

             _freshness_panel(),

             _alerts_panel(),

             "<h2>Emissions by category (2024)</h2>",
             "<div class='card'>%s</div>" % _table(_csv("national_totals_2024.csv"), bold_last=True),

             "<h2>Validation vs FAOSTAT &amp; EDGAR</h2>",
             "<div class='card'>%s</div>" % _table(_benchmark_panel()),

             "<h2>Uncertainty (Monte-Carlo, Approach 2)</h2>",
             "<div class='card'>%s%s</div>"
             % (_table(_csv("uncertainty_montecarlo.csv"), bold_last=True),
                _img("uncertainty_distribution.png")),

             "<h2>AFOLU: agriculture + LULUCF land sector</h2>",
             "<div class='card'>%s%s</div>"
             % (_table(_csv("afolu_summary.csv")),
                "<div class='sub'>LULUCF sub-categories (sink = negative):</div>"
                + _table(_csv("lulucf_totals.csv"), bold_last=True)
                if _csv("lulucf_totals.csv") else ""),

             _key_category_panel(),

             "<h2>By province (agriculture)</h2>",
             "<div class='card'>%s</div>" % _table(_csv("provincial_totals_2024.csv"), bold_last=True),

             "<h2>Where the emissions are (~5 km grid)</h2>",
             "<div class='card'>%s</div>" % _img("hotspot_total.png", "gis"),

             _nowcast_panel(),

             _rice_panel(),

             _soil_n2o_panel(),

             _livestock_panel(),

             _land_change_panel(),

             _district_panel(),

             _system_eval_panel(),

             "<h2>Trend 1990&ndash;2024</h2>",
             "<div class='card'><div class='sub'>%s</div>%s</div>"
             % (_cagr() or "", _img("trend_chart.png")),

             "<h2>CRT-style table (latest year)</h2>",
             "<div class='card'>%s</div>" % _table(crt),

             _completeness_panel(),

             "<h2>Key caveats</h2>",
             "<div class='card'><ul class='flags'>%s</ul></div>"
             % ("".join(flags) if flags else "<li class='missing'>run the inventory for flags</li>"),

             "<div class='foot'>IPCC 2006 GL + 2019 Refinement &middot; AR5 GWP-100 &middot; "
             "every number traces to data/ &middot; see docs/ for methods and tier2_changelog</div>",
             "</div></body></html>"]
    out_path = asset_path(OUT, "dashboard.html")
    os.makedirs(OUT, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    print("wrote outputs/dashboard.html (%d KB)" % (os.path.getsize(out_path) // 1024))


if __name__ == "__main__":
    build()
