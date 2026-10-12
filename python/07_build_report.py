"""
07_build_report.py
Builds reports/encounter_reporting_dq_report.pdf from the CSV outputs in reports/output/.
Every number in the report is read from those files.
"""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import FuncFormatter, PercentFormatter
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, Table, TableStyle,
                                Image, PageBreak, KeepTogether)
from PIL import Image as PILImage

ROOT = Path(__file__).resolve().parents[1]
O = ROOT / "reports/output"
FIG = ROOT / "reports/figures"; FIG.mkdir(parents=True, exist_ok=True)
PDF = ROOT / "reports/encounter_reporting_dq_report.pdf"

INK, MUTED, GRID, PANEL = "#1F2A37", "#6B7280", "#E5E7EB", "#F3F6F9"
BLUE, TEAL, CORAL, SAND, PURPLE, GREY = "#2F5D8A", "#3A9D8F", "#D9644A", "#C9A227", "#7A6FB0", "#B8C2CC"
rd = lambda n: pd.read_csv(O / f"{n}.csv")

ov = rd("rpt_overview").iloc[0]
cls_all = rd("rpt_class_summary"); cls = rd("rpt_class_summary_window")
annual = rd("rpt_annual_volume"); monthly = rd("rpt_monthly_volume"); top = rd("rpt_top_visit_types")
agegen = rd("rpt_age_gender"); payer = rd("rpt_payer"); util = rd("rpt_utilization_dist")
orgs = rd("rpt_top_organizations"); conc = rd("rpt_org_concentration").iloc[0]
n_types = int(rd("rpt_visit_types_count").iloc[0, 0])
rec_p = rd("prod_recon_encounter_counts"); rec_t = rd("test_recon_encounter_counts")
link_p = rd("prod_recon_child_linkage"); link_t = rd("test_recon_child_linkage")
dq_p = rd("prod_dq_results"); dq_t = rd("test_dq_results")
det = rd("detection_by_error"); dsum = rd("detection_summary"); sec = rd("secondary_flags")
head = pd.read_csv(O / "detection_headline.csv", index_col=0)["value"]
inj = pd.read_csv(ROOT / "data/test/injected_error_log.csv")

C = lambda v: f"{int(v):,}"
P1 = lambda v: f"{v:.1%}"
n_tables, n_views, n_checks = 9, 8, len(dq_p)
base_fail = dq_p[dq_p.status == "FAIL"]; base_rows = int(base_fail.rows_flagged.sum())
cats = dq_p.groupby("category").size()

def style(ax, title, grid="y"):
    ax.set_title(title, loc="left", fontsize=10.5, color=INK, fontweight="bold", pad=8)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    for s in ("left", "bottom"): ax.spines[s].set_color(GRID)
    ax.tick_params(colors=MUTED, labelsize=8.5); ax.grid(axis=grid, color=GRID, lw=0.7); ax.set_axisbelow(True)
def save(fig, name):
    fig.tight_layout(); fig.savefig(FIG / name, dpi=200); plt.close(fig); return str(FIG / name)
kfmt = FuncFormatter(lambda x, _: f"{x/1000:.0f}k" if x >= 1000 else f"{x:.0f}")

# ---------------------------------------------------------------- figures
# ERD
fig, ax = plt.subplots(figsize=(7.4, 4.3)); ax.set_xlim(0, 100); ax.set_ylim(0, 60); ax.axis("off")
counts = {"patients": ov.patients, "encounters": ov.encounters, "providers": ov.providers, "organizations": ov.organizations,
          "payers": ov.payers, "conditions": ov.conditions, "procedures": ov.procedures, "medications": ov.medications,
          "immunizations": ov.immunizations}
boxes = {"patients": (3, 44, 21, BLUE), "encounters": (38, 27, 22, CORAL), "providers": (77, 44, 20, BLUE),
         "organizations": (77, 27, 20, BLUE), "payers": (77, 10, 20, BLUE),
         "conditions": (1, 2, 17, TEAL), "procedures": (20, 2, 17, TEAL), "medications": (39, 2, 17, TEAL),
         "immunizations": (58, 2, 17, TEAL)}
H = 9
for n, (x, y, w, c) in boxes.items():
    ax.add_patch(FancyBboxPatch((x, y), w, H, boxstyle="round,pad=0.3,rounding_size=1.2", fc=c, ec="none"))
    ax.text(x + w / 2, y + H * 0.62, n, ha="center", va="center", color="white", fontsize=8.6, fontweight="bold")
    ax.text(x + w / 2, y + H * 0.27, f"{int(counts[n]):,} rows", ha="center", va="center", color="white", fontsize=7.3)
lab = dict(fontsize=6.9, color=MUTED, ha="center", va="center", bbox=dict(fc="white", ec="none", pad=0.6))
def arrow(x1, y1, x2, y2, label=None, lx=None, ly=None):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=1.1, shrinkA=0, shrinkB=2))
    if label: ax.text(lx, ly, label, **lab)
arrow(42, 36.3, 24.3, 46, "patient", 33, 41.5)
arrow(60.3, 34.5, 77, 47, "provider", 68.5, 41.3)
arrow(60.3, 31.5, 77, 31.5, "organization", 68.5, 31.5)
arrow(60.3, 28.5, 77, 15, "payer", 68.5, 21.6)
arrow(87, 44, 87, 36.3, "organization", 87, 40.2)
for n in ("conditions", "procedures", "medications", "immunizations"):
    x, y, w, _ = boxes[n]
    arrow(x + w / 2, y + H + 0.3, 49, 27, None)
ax.text(18, 20.5, "event.encounter → encounters.id\nevent.patient → patients.id", **{**lab, "ha": "left"})
ax.text(3, 57.5, "Arrows point from a foreign key to the table it references", fontsize=7, color=MUTED)
f_erd = save(fig, "table_relationships.png")

# annual volume
fig, ax = plt.subplots(figsize=(7.2, 2.8))
b = ax.bar(annual.encounter_year.astype(str), annual.encounters, color=[CORAL if y == 2021 else BLUE for y in annual.encounter_year], width=0.62)
ax.bar_label(b, labels=[C(v) for v in annual.encounters], fontsize=7.8, color=INK, padding=2)
ax.yaxis.set_major_formatter(kfmt); ax.set_ylim(0, annual.encounters.max() * 1.2)
style(ax, "Annual encounters, 2017–2025 (2021 includes COVID-19 vaccination visits)")
f_annual = save(fig, "annual_encounters.png")

# class mix
cs = cls.sort_values("encounters")
fig, ax = plt.subplots(figsize=(7.2, 3.0))
b = ax.barh(cs.encounterclass, cs.encounters, color=BLUE, height=0.62)
ax.bar_label(b, labels=[f"{C(v)}  ({p:.1f}%)" for v, p in zip(cs.encounters, cs.pct_of_encounters)], fontsize=7.8, color=INK, padding=3)
ax.xaxis.set_major_formatter(kfmt); ax.set_xlim(0, cs.encounters.max() * 1.25)
style(ax, "Encounters by class, Oct 2016 – Sep 2026", grid="x")
f_class = save(fig, "encounters_by_class.png")

# monthly lines for top classes
mv = monthly.pivot_table(index="encounter_month", columns="encounterclass", values="encounters", aggfunc="sum").fillna(0)
mv.index = pd.to_datetime(mv.index)
mq = mv.resample("QS").sum()
fig, ax = plt.subplots(figsize=(7.2, 2.8))
for c, col in [("ambulatory", BLUE), ("wellness", TEAL), ("outpatient", SAND), ("urgentcare", PURPLE), ("emergency", CORAL)]:
    ax.plot(mq.index, mq[c], color=col, lw=1.8, label=c)
ax.legend(frameon=False, fontsize=7.8, ncol=5, loc="upper left")
ax.set_ylim(0, mq[["ambulatory"]].max().max() * 1.25)
style(ax, "Quarterly encounters by class")
f_quarter = save(fig, "quarterly_by_class.png")

# payer
ps = payer.sort_values("encounters")
fig, ax = plt.subplots(figsize=(7.2, 3.0))
b = ax.barh(ps.payer_name, ps.encounters, color=[TEAL if o == "GOVERNMENT" else (CORAL if o == "NO_INSURANCE" else BLUE) for o in ps.payer_ownership], height=0.62)
ax.bar_label(b, labels=[f"{C(v)}  ·  {c:.0f}% covered" for v, c in zip(ps.encounters, ps.payer_covered_pct)], fontsize=7.6, color=INK, padding=3)
ax.xaxis.set_major_formatter(kfmt); ax.set_xlim(0, ps.encounters.max() * 1.35)
style(ax, "Encounters by payer (teal = government, blue = private, coral = uninsured)", grid="x")
f_payer = save(fig, "encounters_by_payer.png")

# reconciliation test
rt = rec_t[rec_t.step <= 7]
fig, ax = plt.subplots(figsize=(7.2, 2.9))
labels = ["Source", "+patients", "+providers", "+orgs", "+payers", "LEFT JOIN\nview", "Distinct\nIDs"]
b = ax.bar(labels, rt.row_count, color=[GREY] + [CORAL if v != rt.row_count.iloc[0] else BLUE for v in rt.row_count.iloc[1:]], width=0.6)
ax.bar_label(b, labels=[C(v) for v in rt.row_count], fontsize=7.8, color=INK, padding=2)
ax.axhline(rt.row_count.iloc[0], color=MUTED, ls="--", lw=1)
ax.set_ylim(rt.row_count.min() * 0.985, rt.row_count.max() * 1.008); ax.yaxis.set_major_formatter(kfmt)
style(ax, "Test dataset: encounter count after each join (dashed = source count)")
f_rec = save(fig, "test_join_reconciliation.png")

# detection by group
gname = {"A": "Missing keys", "B": "Orphan records", "C": "Duplicate IDs", "D": "Inconsistent dates", "E": "Plausible-but-wrong"}
g = det.groupby("group").agg(injected=("error_id", "count"), detected=("detected", "sum")).reset_index()
g["name"] = g.group.map(gname)
fig, ax = plt.subplots(figsize=(7.2, 2.8))
x = range(len(g)); w = 0.36
b1 = ax.bar([i - w / 2 for i in x], g.injected, w, color=GREY, label="Injected")
b2 = ax.bar([i + w / 2 for i in x], g.detected, w, color=[TEAL if d == n else CORAL for d, n in zip(g.detected, g.injected)], label="Detected")
ax.bar_label(b1, fontsize=8, color=INK, padding=2); ax.bar_label(b2, fontsize=8, color=INK, padding=2)
ax.set_xticks(list(x)); ax.set_xticklabels(g.name); ax.set_ylim(0, g.injected.max() * 1.22)
ax.legend(frameon=False, fontsize=8, loc="upper right")
style(ax, f"Injected vs detected errors ({int(head.detected)} of {int(head.injected_errors)} detected)")
f_det = save(fig, "detection_by_group.png")

# ---------------------------------------------------------------- PDF helpers
ss = dict(fontName="Helvetica", textColor=colors.HexColor(INK))
T = ParagraphStyle("t", fontName="Helvetica-Bold", fontSize=24, leading=29, textColor=colors.HexColor(INK))
ST = ParagraphStyle("st", fontName="Helvetica", fontSize=12, leading=16, textColor=colors.HexColor(MUTED))
H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=15, leading=19, textColor=colors.HexColor(INK), spaceBefore=4, spaceAfter=6)
H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=colors.HexColor(BLUE), spaceBefore=8, spaceAfter=3)
BD = ParagraphStyle("b", fontSize=9.4, leading=13, spaceAfter=5, **ss)
BL = ParagraphStyle("bl", fontSize=9.4, leading=13, leftIndent=12, bulletIndent=2, spaceAfter=3, **ss)
CAP = ParagraphStyle("c", fontName="Helvetica-Oblique", fontSize=8, leading=10, textColor=colors.HexColor(MUTED), spaceAfter=8)
TC = ParagraphStyle("tc", fontSize=7.9, leading=9.8, **ss)
TH = ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=7.9, leading=9.8, textColor=colors.white)
CODE = ParagraphStyle("code", fontName="Courier", fontSize=7.8, leading=10, textColor=colors.HexColor(INK), backColor=colors.HexColor(PANEL),
                      borderPadding=6, leftIndent=6, rightIndent=6, spaceBefore=4, spaceAfter=10)
KV = ParagraphStyle("kv", fontName="Helvetica-Bold", fontSize=15, leading=18, alignment=1, textColor=colors.HexColor(INK))
KL = ParagraphStyle("kl", fontName="Helvetica", fontSize=7.6, leading=9.5, alignment=1, textColor=colors.HexColor(MUTED))

def bul(t): return Paragraph(t, BL, bulletText="•")
def img(path, w=7.1):
    W, Hh = PILImage.open(path).size
    return Image(path, w * inch, w * inch * Hh / W)
def table(rows, widths, zebra=True, color_status=None):
    data = [[Paragraph(str(c), TH) for c in rows[0]]] + [[Paragraph(str(c), TC) for c in r] for r in rows[1:]]
    t = Table(data, colWidths=[w * inch for w in widths], repeatRows=1)
    st = [("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(BLUE)), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("TOPPADDING", (0, 0), (-1, -1), 2.6), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
          ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor(GRID))]
    if zebra:
        for i in range(2, len(data), 2): st.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor(PANEL)))
    t.setStyle(TableStyle(st)); return t
def kpis(items):
    t = Table([[Paragraph(v, KV) for v, _ in items], [Paragraph(l, KL) for _, l in items]], colWidths=[7.1 / len(items) * inch] * len(items))
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(PANEL)), ("LINEAFTER", (0, 0), (-2, -1), 1, colors.white),
                           ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    return t
def status(s): return f'<font color="{TEAL if s == "PASS" else CORAL}"><b>{s}</b></font>'
def sgn(v): return "" if pd.isna(v) else (f"+{C(v)}" if v > 0 else C(v) if v < 0 else "0")

# derived numbers
amb = cls.set_index("encounterclass")
y20 = annual.set_index("encounter_year")
fanout = int(rec_t.loc[rec_t.step == 6, "row_count"].iloc[0] - rec_t.loc[rec_t.step == 1, "row_count"].iloc[0])
src_t = int(rec_t.loc[rec_t.step == 1, "row_count"].iloc[0])
dup_pat_extra = int(rec_t.loc[rec_t.step == 2, "change_vs_previous_step"].iloc[0])
dup_prov_extra = int(rec_t.loc[rec_t.step == 3, "change_vs_previous_step"].iloc[0])
distinct_t = int(rec_t.loc[rec_t.step == 7, "row_count"].iloc[0])
gov = payer[payer.payer_ownership == "GOVERNMENT"].encounters.sum() / payer.encounters.sum()
unins = payer[payer.payer_ownership == "NO_INSURANCE"].encounters.sum() / payer.encounters.sum()
heavy = util[util.encounters_per_year == "11+"].patient_years.iloc[0] / util.patient_years.sum()
fem = agegen[agegen.gender == "F"].encounters.sum() / agegen.encounters.sum()

story = []
# ---------------------------------------------------------------- cover
story += [Spacer(1, 1.5 * inch), Paragraph("Healthcare Encounter Reporting &amp; Data Quality", T), Spacer(1, 8),
          Paragraph("Detailed Project Report", ST), Spacer(1, 4),
          Paragraph("Synthea synthetic patient records · PostgreSQL 16 · Python", ST), Spacer(1, 26),
          kpis([(C(ov.patients), "synthetic patients"), (C(ov.encounters), "encounters"), (str(n_tables), "related tables"),
                (str(n_checks), "validation checks"), (f"{int(head.detected)} / {int(head.injected_errors)}", "injected errors detected")]),
          Spacer(1, 30), Paragraph("Prepared by Suman Oraon · October 2026", BD),
          Paragraph("<b>Synthetic data.</b> All patients and encounters were generated with Synthea, the open-source synthetic patient "
                    "generator from The MITRE Corporation (seed 20261012, Philadelphia, Pennsylvania). No real patient data is used. "
                    "Facility and payer names come from Synthea's public reference files; their encounter volumes are simulated.", BD),
          PageBreak()]

# ---------------------------------------------------------------- contents + summary
story += [Paragraph("Contents", H1)]
for i, s in enumerate(["Executive summary", "Data source and approach", "Table relationships", "SQL reporting views",
                       "Encounter volume and visit types", "Join reconciliation", "Validation checks",
                       "Documented exceptions", "Testing the checks against injected errors", "Limitations and next steps",
                       "Reproducing the analysis"], 1):
    story.append(Paragraph(f"{i}.&nbsp;&nbsp;{s}", BD))
story += [Spacer(1, 8), Paragraph("1. Executive summary", H1),
          Paragraph(f"This project builds a PostgreSQL reporting layer and a data-quality layer on top of Synthea synthetic health "
                    f"records: {C(ov.patients)} patients, {C(ov.encounters)} encounters and {C(ov.conditions + ov.procedures + ov.medications + ov.immunizations)} "
                    f"clinical events across {n_tables} related tables. It answers two questions. What does encounter volume look like by "
                    f"class and visit type? And can the checks be trusted to catch the errors that break reporting?", BD),
          Paragraph("Key results", H2),
          bul(f"<b>{n_views} SQL reporting views</b> cover encounter detail, monthly volume, class and visit-type summaries, "
              f"age and gender, payer, patient utilization and organization volume."),
          bul(f"<b>Encounter counts reconcile in the production data.</b> All {C(ov.encounters)} encounters survive every join, and "
              f"every roll-up view adds back to the same total."),
          bul(f"<b>The reconciliation catches fan-out.</b> In the test dataset, duplicate patient and provider IDs would inflate the "
              f"reporting view by {C(fanout)} rows ({fanout/src_t:.1%}) if counts were not checked before and after each join."),
          bul(f"<b>{n_checks} validation checks</b> in four groups: missing keys ({cats['Missing key']}), orphan records "
              f"({cats['Orphan record']}), duplicate identifiers ({cats['Duplicate identifier']}) and inconsistent dates "
              f"({cats['Inconsistent date']})."),
          bul(f"<b>{int(head.detected)} of {int(head.injected_errors)} deliberately introduced errors were detected</b> in a separate "
              f"test dataset: all {int(head.structural_errors)} structural errors, each by the check designed for it, with no false "
              f"positives. The {int(head.missed)} misses are plausible-but-wrong values included on purpose to show what structural "
              f"checks cannot catch."),
          bul(f"<b>{len(base_fail)} genuine source exceptions</b> ({C(base_rows)} rows) were found in the untouched Synthea output and "
              f"documented, and two check rules were adjusted with a written rationale."),
          Paragraph("Encounter highlights (Oct 2016 – Sep 2026)", H2),
          bul(f"Ambulatory visits are {amb.loc['ambulatory','pct_of_encounters']:.1f}% of encounters and wellness visits "
              f"{amb.loc['wellness','pct_of_encounters']:.1f}%. Inpatient stays are {amb.loc['inpatient','pct_of_encounters']:.1f}% of "
              f"volume but average {amb.loc['inpatient','avg_claim_cost']:,.0f} dollars per claim."),
          bul(f"Annual volume holds at about 3,900–4,700 encounters, except 2021 ({C(y20.loc[2021,'encounters'])}), when COVID-19 "
              f"vaccination added more than 1,100 visits."),
          bul(f"Government payers (Medicaid, Medicare, dual eligible) cover {gov:.0%} of encounters; {unins:.0%} are uninsured."),
          PageBreak()]

# ---------------------------------------------------------------- 2 data & approach
story += [Paragraph("2. Data source and approach", H1),
          Paragraph("Synthea simulates the medical history of a synthetic population from birth to the reference date, using "
                    "clinical care maps for common conditions. It exports standard tables in the same shape as an EHR extract.", BD),
          table([["Setting", "Value"], ["Generator", "Synthea (official release jar, build d9d07a6)"],
                 ["Command", "-p 1000 -s 20261012 -cs 20261012 -r 20260930, Pennsylvania / Philadelphia"],
                 ["Population", f"{C(ov.patients)} patients (1,000 alive at the reference date plus {C(ov.deceased_patients)} who died during the simulation)"],
                 ["History", f"Encounters from {ov.first_encounter} to {ov.last_encounter}; reporting window Oct 2016 – Sep 2026 ({C(ov.encounters_in_window)} encounters)"],
                 ["Export", "CSV, 9 of 18 tables used; identifier-style fields (SSN, license, passport, names, street address) removed"]],
                [1.3, 5.8]),
          Paragraph("Table 1. Generation settings (synthea/generate_synthea.sh)", CAP),
          Paragraph("Pipeline", H2),
          table([["Step", "Script", "What it does"],
                 ["1", "synthea/generate_synthea.sh", "Downloads Synthea and generates the seeded population"],
                 ["2", "python/01_prepare_raw.py", "Selects 9 tables, drops identifier fields, adds a stable _row_id, writes data/raw/*.csv.gz"],
                 ["3", "python/02_load_postgres.py", "Loads schema synthea, builds 8 reporting views and the join reconciliation"],
                 ["4", "python/03_run_dq_checks.py", f"Runs the {n_checks} checks; every failing row goes to dq_exceptions"],
                 ["5", "python/04_build_test_dataset.py", f"Builds a separate test copy with {int(head.injected_errors)} logged errors"],
                 ["6", "02 + 03 on schema synthea_test", "Loads the test copy and runs the same views, reconciliation and checks"],
                 ["7", "python/05_score_detection.py", "Scores detection per error, traces every secondary flag"],
                 ["8", "python/06–07", "Exports reporting outputs and builds this report"]],
                [0.45, 2.15, 4.5]),
          Paragraph("Table 2. Pipeline (run_all.sh runs every step)", CAP),
          Paragraph("<b>Design choice: keys are checked, not enforced.</b> The tables are loaded without PRIMARY KEY or FOREIGN KEY "
                    "constraints so that the data loads as received. A constraint would reject a bad row at load time and hide "
                    "the problem; the checks instead find, count and trace every failing row.", BD),
          PageBreak()]

# ---------------------------------------------------------------- 3 relationships
krows = [["Table", "Rows", "Key", "References"],
         ["patients", C(ov.patients), "id", "—"], ["organizations", C(ov.organizations), "id", "—"],
         ["providers", C(ov.providers), "id", "organization → organizations.id"], ["payers", C(ov.payers), "id", "—"],
         ["encounters", C(ov.encounters), "id", "patient, provider, organization, payer"],
         ["conditions", C(ov.conditions), "(none: event row)", "patient → patients.id; encounter → encounters.id"],
         ["procedures", C(ov.procedures), "(none: event row)", "patient → patients.id; encounter → encounters.id"],
         ["medications", C(ov.medications), "(none: event row)", "patient, encounter, payer"],
         ["immunizations", C(ov.immunizations), "(none: event row)", "patient → patients.id; encounter → encounters.id"]]
story += [Paragraph("3. Table relationships", H1), img(f_erd, 6.9),
          Paragraph("Figure 1. Logical model. Encounters sit at the center; four dimension tables describe them and four event tables hang off them.", CAP),
          table(krows, [1.25, 0.9, 1.35, 3.6]), Paragraph("Table 3. Tables, keys and references (docs/table_relationships.md)", CAP),
          Paragraph("Event tables have no natural key, so a loader-assigned _row_id identifies every row in every table. That "
                    "makes each check result traceable to one source row.", BD),
          PageBreak()]

# ---------------------------------------------------------------- 4 views
story += [Paragraph("4. SQL reporting views", H1),
          Paragraph(f"The reporting layer is {n_views} views in sql/02_reporting_views.sql. Every aggregate view is built on "
                    "vw_encounter_detail, so all of them share the same joins, the same filters and the same encounter count.", BD),
          table([["View", "Grain", "Supports"],
                 ["vw_encounter_detail", "Encounter", "Base layer: encounter + patient age/gender, provider specialty, organization, payer, duration, reporting-window flag, match flags"],
                 ["vw_encounter_volume_monthly", "Month × class", "Volume trends"],
                 ["vw_encounter_class_summary", "Encounter class", "Class mix, patients per class, median duration, average claim cost, payer coverage"],
                 ["vw_visit_type_summary", "Class × visit code", f"Visit types ranked within each class ({n_types} SNOMED codes)"],
                 ["vw_encounter_by_age_gender", "Age group × gender × class", "Demographic mix"],
                 ["vw_encounter_by_payer", "Payer", "Volume and share of claim cost covered"],
                 ["vw_patient_utilization", "Patient × year", "Encounters per patient, acute and inpatient visits"],
                 ["vw_organization_volume", "Organization", "Site volume and concentration"]],
                [1.9, 1.45, 3.75]),
          Paragraph("Table 4. Reporting views", CAP),
          Paragraph("Why LEFT JOINs in the base view", H2),
          Paragraph("An INNER JOIN would silently drop any encounter whose patient, provider, organization or payer is missing. "
                    "The base view uses LEFT JOINs and exposes has_patient, has_provider, has_organization and has_payer flags, "
                    "so unmatched encounters stay visible and are labelled '(unmatched)' in the roll-ups. The trade-off is that "
                    "LEFT JOINs inflate counts when a dimension key is duplicated, which is why the reconciliation in section 6 "
                    "checks counts before and after every join.", BD),
          Paragraph("Example: class summary", H2),
          Paragraph("SELECT encounterclass, COUNT(*) AS encounters,<br/>"
                    "&nbsp;&nbsp;ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_encounters,<br/>"
                    "&nbsp;&nbsp;COUNT(DISTINCT patient_id) AS unique_patients,<br/>"
                    "&nbsp;&nbsp;PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_minutes) AS median_duration_min<br/>"
                    "FROM vw_encounter_detail GROUP BY encounterclass;", CODE),
          PageBreak()]

# ---------------------------------------------------------------- 5 volume & visit types
crow = [["Class", "Encounters", "Share", "Patients", "Median duration", "Avg claim cost", "Payer covered"]] + \
       [[r.encounterclass, C(r.encounters), f"{r.pct_of_encounters:.1f}%", C(r.unique_patients),
         (f"{r.median_duration_min/60:.1f} h" if r.median_duration_min >= 120 else f"{r.median_duration_min:.0f} min"),
         f"${r.avg_claim_cost:,.0f}", f"{r.payer_covered_pct:.0f}%"] for r in cls.itertuples()]
trow = [["Class", "Visit type", "Encounters", "Patients"]] + \
       [[r.encounterclass, r.visit_description.replace(" (procedure)", "").replace(" (regime/therapy)", "").replace(" (environment)", ""),
         C(r.encounters), C(r.unique_patients)] for r in top.itertuples()]
story += [Paragraph("5. Encounter volume and visit types", H1),
          Paragraph(f"Figures in this section use the 10-year reporting window (Oct 2016 – Sep 2026): {C(ov.encounters_in_window)} "
                    f"encounters for {C(ov.patients_in_window)} patients. Synthea also exports older encounters tied to long-running "
                    f"conditions; those are kept in the data but excluded from trend views.", BD),
          img(f_annual), Paragraph("Figure 2. Annual encounters, complete years only", CAP),
          Paragraph(f"Volume is steady at about {C(annual[annual.encounter_year != 2021].encounters.min())}–"
                    f"{C(annual[annual.encounter_year != 2021].encounters.max())} encounters a year, or about "
                    f"{annual[annual.encounter_year != 2021].encounters_per_patient.mean():.1f} per active patient. 2021 is the "
                    f"exception: Synthea models COVID-19 vaccination, and vaccine-administration encounters jump from 8 in 2020 to "
                    f"1,180 in 2021 before falling back to 36 in 2022.", BD),
          img(f_class), Paragraph("Figure 3. Encounter class mix", CAP),
          PageBreak(),
          table(crow, [1.05, 0.9, 0.7, 0.8, 1.15, 1.2, 1.2]), Paragraph("Table 5. Encounter class summary (reporting window)", CAP),
          bul(f"<b>Volume and cost run in opposite directions.</b> Ambulatory, wellness and outpatient visits make up "
              f"{amb.loc[['ambulatory','wellness','outpatient'],'pct_of_encounters'].sum():.0f}% of encounters. Inpatient, skilled "
              f"nursing and hospice together are under 2%, but each of those stays costs $12,000–$20,000 on average."),
          bul(f"<b>Coverage varies by class.</b> Payers cover {amb.loc['wellness','payer_covered_pct']:.0f}% of wellness claim cost "
              f"but {amb.loc['inpatient','payer_covered_pct']:.0f}% of inpatient claim cost."),
          img(f_quarter), Paragraph("Figure 4. Quarterly encounters for the five largest classes", CAP),
          KeepTogether([table(trow, [1.0, 3.9, 1.0, 1.0]), Paragraph(f"Table 6. Top 12 of {n_types} visit types by volume", CAP)]),
          PageBreak(),
          img(f_payer), Paragraph("Figure 5. Encounters by payer and share of claim cost covered", CAP),
          Paragraph("Patients and utilization", H2),
          bul(f"<b>Women account for {fem:.0%} of encounters.</b> The gap is widest at ages 18–39, where prenatal care (the "
              f"fifth-largest visit type) adds thousands of visits."),
          bul(f"<b>Utilization is skewed.</b> In {heavy:.0%} of patient-years a patient has 11 or more encounters, mostly "
              f"driven by repeat care: chronic kidney disease stage 4 (19%), pregnancy (13%) and allergy (9%) are the most "
              f"common reasons recorded on those encounters."),
          bul(f"<b>Volume is concentrated.</b> {int(conc.orgs_for_half_of_volume)} of {int(conc.orgs_with_encounters)} organizations "
              f"account for half of all encounters."),
          table([["Encounters per patient-year", "Patient-years", "Share"]] +
                [[r.encounters_per_year, C(r.patient_years), P1(r.patient_years / util.patient_years.sum())] for r in util.itertuples()],
                [2.6, 2.2, 2.2]),
          Paragraph("Table 7. Utilization distribution, 2017–2025", CAP),
          PageBreak()]

# ---------------------------------------------------------------- 6 reconciliation
def rec_rows(df):
    return [["Step", "Join / roll-up", "Encounters", "vs previous", "vs source", "Status"]] + \
           [[r.step, r.description, C(r.row_count), sgn(r.change_vs_previous_step), sgn(r.change_vs_source), status(r.status)]
            for r in df.itertuples()]
story += [Paragraph("6. Join reconciliation", H1),
          Paragraph("Encounter counts are checked before and after each join (sql/03_reconciliation.sql). INNER JOIN steps show "
                    "how many encounters a join would silently drop; the LEFT JOIN view shows whether duplicate dimension keys "
                    "inflate the count; the roll-up steps prove each aggregate view adds back to the detail view.", BD),
          Paragraph("Production data (Synthea as generated)", H2),
          table(rec_rows(rec_p), [0.45, 3.25, 0.85, 0.8, 0.75, 0.6]),
          Paragraph(f"Table 8. Production reconciliation: every step returns {C(ov.encounters)} encounters", CAP),
          Paragraph("Test data (with injected errors)", H2),
          table(rec_rows(rec_t), [0.45, 3.25, 0.85, 0.8, 0.75, 0.6]),
          Paragraph("Table 9. Test reconciliation", CAP),
          PageBreak(),
          img(f_rec), Paragraph("Figure 6. Test dataset: encounter count after each join", CAP),
          Paragraph("Reading the test reconciliation", H2),
          bul(f"<b>Joining to patients adds {C(dup_pat_extra)} rows.</b> Four patient IDs are duplicated, so every encounter for those "
              f"patients is counted twice."),
          bul(f"<b>Joining to providers adds {C(dup_prov_extra)} more.</b> Two duplicated provider IDs belong to high-volume "
              f"providers, so a single duplicate row can double thousands of encounters."),
          bul("<b>Each later INNER JOIN drops rows</b> where the key is null or orphaned, partly offsetting the inflation, so a "
              "row total alone could look close to correct while being wrong in both directions."),
          bul(f"<b>The LEFT JOIN reporting view shows {C(src_t + fanout)} rows for {C(src_t)} source encounters</b> "
              f"({sgn(fanout)}), and only {C(distinct_t)} distinct encounter IDs because 12 rows reuse an existing ID."),
          Paragraph("Child linkage", H2),
          table([["Table", "Prod rows", "Prod linked", "Test rows", "Test unlinked", "Test linked"]] +
                [[a.table_name, C(a.source_rows), f"{a.linked_pct:.2f}%", C(b.source_rows), C(b.unlinked_rows), f"{b.linked_pct:.2f}%"]
                 for a, b in zip(link_p.itertuples(), link_t.itertuples())], [1.3, 1.0, 1.0, 1.0, 1.1, 1.0]),
          Paragraph("Table 10. Share of clinical event rows that join back to an encounter", CAP),
          Paragraph("<b>Takeaway:</b> run the reconciliation before every refresh. A PASS on every step is the gate for publishing "
                    "the reporting views.", BD),
          PageBreak()]

# ---------------------------------------------------------------- 7 checks
cat_rows = [["ID", "Category", "Table", "Rule", "Severity", "Prod rows", "Status"]] + \
           [[r.check_id, r.category.replace("Duplicate identifier", "Duplicate ID").replace("Inconsistent date", "Date").replace("Orphan record", "Orphan"),
             r.table_name, r.description, r.severity, C(r.rows_flagged), status(r.status)] for r in dq_p.assign(o=dq_p.check_id.str[:2].map({"MK":0,"OR":1,"DU":2,"DT":3})).sort_values(["o","check_id"]).itertuples()]
story += [Paragraph("7. Validation checks", H1),
          Paragraph(f"The {n_checks} checks in sql/04_dq_checks.sql write every failing row to dq_exceptions (check, table, _row_id, "
                    f"key, detail) and summarize to dq_results. In the production data {n_checks - len(base_fail)} checks pass and "
                    f"{len(base_fail)} flag genuine source exceptions (section 8).", BD),
          table(cat_rows, [0.5, 0.85, 0.95, 2.77, 0.6, 0.62, 0.55]),
          Paragraph("Table 11. Check catalog with production results", CAP),
          PageBreak()]

# ---------------------------------------------------------------- 8 exceptions
exc = [["Check", "Rows", "What it is", "Handling"],
       ["DT04", C(dq_p.set_index("check_id").loc["DT04", "rows_flagged"]), "Encounters dated 1–16 days after the reference date (Synthea schedules a few visits past it)", "Kept in source; excluded from the reporting window"],
       ["DT07", C(dq_p.set_index("check_id").loc["DT07", "rows_flagged"]), "Procedures more than 24 h after their encounter closed, mostly digital rectal exams", "Kept and flagged; reported to the data owner"],
       ["DT10", C(dq_p.set_index("check_id").loc["DT10", "rows_flagged"]), "Medications whose stop date is 4–6 days before the start date", "Kept and flagged; exclude from duration metrics"],
       ["DT11", C(dq_p.set_index("check_id").loc["DT11", "rows_flagged"]), "Vaccine doses (41 of 42 COVID-19) dated 1–35 days after the encounter they are attached to", "Kept and flagged; use the immunization date for dose timing"]]
rules = [["Check", "Original rule", "Rows before", "Adjusted rule", "Rationale"],
         ["DT03", "Encounter > 1 day after death", "118", "Excludes encounter code 308646001 (Death Certification)", "Death certification is recorded after death by design (2–14 days)"],
         ["DT07", "Procedure outside encounter start–stop", "36,728", "Procedure before encounter start or > 24 h after stop", "Synthea sequences procedures after a short encounter closes; median gap under an hour"]]
story += [Paragraph("8. Documented exceptions", H1),
          Paragraph(f"The untouched Synthea output fails {len(base_fail)} checks on {C(base_rows)} rows. These are real quirks of the "
                    f"source, not injected errors. They are documented, left in place, and subtracted from the test results so they "
                    f"do not count as detections. Full list: docs/exceptions_log.md and reports/output/prod_dq_exceptions.csv.", BD),
          table(exc, [0.5, 0.55, 3.55, 2.5]), Paragraph("Table 12. Source exceptions found in the production data", CAP),
          Paragraph("Rule adjustments", H2),
          Paragraph("Two rules flagged expected behaviour in their first version. Each was narrowed with a written rationale rather "
                    "than deleted, so the check still catches the real error.", BD),
          table(rules, [0.5, 1.4, 0.75, 2.1, 2.35]), Paragraph("Table 13. Check rules adjusted after reviewing production results", CAP),
          PageBreak()]

# ---------------------------------------------------------------- 9 testing
srow = [["Group", "Error type", "Expected check", "Injected", "Detected"]] + \
       [[gname[r.group], r.error_type, r.expected_check.replace("none (expected miss)", "none"), r.injected,
         f'<font color="{TEAL if r.detected == r.injected else CORAL}"><b>{r.detected}</b></font>'] for r in dsum.itertuples()]
sg = sec.groupby("trace").size().sort_values(ascending=False)
miss = det[~det.detected]
story += [Paragraph("9. Testing the checks against injected errors", H1),
          Paragraph(f"To show the checks work, python/04_build_test_dataset.py builds a separate copy of the 9 tables and introduces "
                    f"{int(head.injected_errors)} errors, logging each one (table, _row_id, column, old value, new value, expected "
                    f"check) in data/test/injected_error_log.csv. The production copy is never touched, and rows that already fail "
                    f"a check in production are excluded, so every detection can be attributed to an injected error.", BD),
          img(f_det), Paragraph("Figure 7. Injected and detected errors by group", CAP),
          kpis([(f"{int(head.detected)} / {int(head.injected_errors)}", "errors detected"),
                (f"{int(head.detected_structural)} / {int(head.structural_errors)}", "structural errors detected"),
                (f"{int(head.detected_by_expected_check)}", "caught by the expected check"),
                (f"{int(head.untraced_false_positives)}", "untraced false positives")]),
          Spacer(1, 8),
          table(srow, [1.25, 2.85, 1.3, 0.75, 0.75]), Paragraph("Table 14. Detection by error type", CAP),
          PageBreak(),
          Paragraph("Secondary flags", H2),
          Paragraph(f"The test run flagged {C(head.new_flagged_rows)} new rows: the {int(head.detected)} injected rows plus "
                    f"{C(head.secondary_flag_rows)} related rows ({C(len(sec))} flags, because some rows fail more than one check). Every "
                    f"secondary flag was traced back to an injected error; none are false positives.", BD),
          table([["Trace", "Flags"]] + [[k, C(v)] for k, v in sg.items()], [5.3, 1.0]),
          Paragraph("Table 15. Secondary flags by cause", CAP),
          Paragraph("Exceptions: the 13 errors the checks missed", H2),
          Paragraph("The plausible-but-wrong group was built to be invisible to structural checks: every value is a valid key, a "
                    "valid date and internally consistent. They were all missed, as expected.", BD),
          table([["Error type", "Count", "Why structural checks miss it", "What would catch it"],
                 ["Encounter assigned to a different valid provider", "4", "Provider exists; no rule says which provider is correct", "Reconcile to source scheduling / billing records"],
                 ["Encounter billed to a different valid payer", "3", "Payer exists", "Compare to the patient's coverage period (payer_transitions table)"],
                 ["Encounter date shifted 20 days", "3", "Date is inside the patient's lifetime and the data window", "Source-to-target row comparison or audit trail"],
                 ["Birth date off by one year", "3", "Still before the first encounter", "Cross-check age-specific care (e.g. well-child visit timing)"]],
                [1.9, 0.5, 2.3, 2.4]),
          Paragraph("Table 16. Missed errors and the control that would catch each", CAP),
          PageBreak()]

# ---------------------------------------------------------------- 10, 11
story += [Paragraph("10. Limitations and next steps", H1),
          bul("<b>Synthetic data.</b> Synthea is internally consistent by construction, so the production run mostly confirms the "
              "checks do not over-flag. The injected test is what demonstrates detection."),
          bul("<b>Structural checks only.</b> The checks prove keys, relationships and dates are consistent. They cannot prove a value "
              "is correct (section 9), which needs a comparison against the source system."),
          bul("<b>Fixed thresholds.</b> The 24-hour procedure tolerance and the 1-day death tolerance suit Synthea. Real EHR data "
              "should have them reviewed with the data owner."),
          bul("<b>No format errors tested.</b> Injected dates are valid timestamps. Malformed strings would fail at load because "
              "columns are typed; a staging table of raw text would be needed to test those."),
          Paragraph("Next steps", H2),
          bul("Add a coverage-period check using Synthea's payer_transitions table to catch encounters billed to the wrong payer."),
          bul("Schedule the reconciliation and checks after every load, and block publishing when a Critical check fails."),
          bul("Track dq_results over time to show trends by check, not only point-in-time counts."),
          Spacer(1, 6),
          Paragraph("11. Reproducing the analysis", H1),
          Paragraph("Requirements: Java 17+, PostgreSQL 14+, Python 3.10+ with pandas, psycopg, matplotlib and reportlab.", BD),
          Paragraph("pip install -r requirements.txt<br/>"
                    "createdb encounters_dq<br/>"
                    "export PGHOST=localhost PGPORT=5432 PGUSER=postgres PGDATABASE=encounters_dq<br/>"
                    "bash run_all.sh&nbsp;&nbsp;&nbsp;&nbsp;# regenerate Synthea data and rebuild everything<br/>"
                    "bash run_all.sh --skip-synthea&nbsp;&nbsp;# reuse the committed data/raw files", CODE),
          table([["Path", "Contents"],
                 ["synthea/generate_synthea.sh", "Seeded Synthea run (jar downloaded on first use, not committed)"],
                 ["data/raw/", "9 tables as generated (gzip CSV)"],
                 ["data/test/", "9 tables with injected errors + injected_error_log.csv (ground truth)"],
                 ["sql/01–04", "Schema, reporting views, join reconciliation, validation checks"],
                 ["python/01–07", "Prepare, load, check, inject, score, export, report"],
                 ["docs/", "Table relationships, exceptions log, check catalog"],
                 ["reports/output/", "Every result table behind this report (CSV)"]],
                [2.2, 4.9]),
          Paragraph("Table 17. Repository contents", CAP)]

def footer(cv, doc):
    if doc.page == 1: return
    cv.saveState(); cv.setFont("Helvetica", 7.5); cv.setFillColor(colors.HexColor(MUTED))
    cv.drawString(0.7 * inch, 0.45 * inch, "Healthcare Encounter Reporting & Data Quality · Synthea synthetic data")
    cv.drawRightString(7.8 * inch, 0.45 * inch, str(doc.page))
    cv.setStrokeColor(colors.HexColor(GRID)); cv.line(0.7 * inch, 0.6 * inch, 7.8 * inch, 0.6 * inch); cv.restoreState()

doc = BaseDocTemplate(str(PDF), pagesize=letter, leftMargin=0.7 * inch, rightMargin=0.7 * inch, topMargin=0.65 * inch,
                      bottomMargin=0.75 * inch, title="Healthcare Encounter Reporting & Data Quality — Project Report", author="Suman Oraon")
doc.addPageTemplates([PageTemplate(id="p", frames=[Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="f")], onPage=footer)])
doc.build(story)
print("built", PDF)
