
import csv
import gzip
import html
import json
from collections import Counter
from pathlib import Path


def open_text(path: str | Path):
    path = Path(path)
    return gzip.open(path, "rt", encoding="utf-8") if path.suffix == ".gz" else path.open(
        "r", encoding="utf-8"
    )


def parse_info(raw: str) -> dict[str, str]:
    result = {}
    for item in raw.split(";"):
        if "=" in item:
            key, value = item.split("=", 1)
            result[key] = value
    return result


def parse_vcf(path: str | Path) -> list[dict]:
    records = []
    with open_text(path) as handle:
        for line in handle:
            if line.startswith("#"):
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) < 8:
                continue
            chrom, pos, record_id, ref, alt, qual, filt, info_raw = fields[:8]
            info = parse_info(info_raw)
            if "SVTYPE" in info:
                variant_type = info["SVTYPE"]
            elif len(ref) == 1 and all(len(value) == 1 for value in alt.split(",")):
                variant_type = "SNP"
            elif len(ref) > max(len(value) for value in alt.split(",")):
                variant_type = "DEL"
            elif len(ref) < max(len(value) for value in alt.split(",")):
                variant_type = "INS"
            else:
                variant_type = "COMPLEX"
            end = int(info.get("END", pos))
            records.append(
                {
                    "chrom": chrom,
                    "pos": int(pos),
                    "end": end,
                    "id": record_id,
                    "ref": ref,
                    "alt": alt,
                    "qual": qual,
                    "filter": filt,
                    "type": variant_type,
                    "info": info_raw,
                }
            )
    return records


def parse_flagstat(path: str | Path) -> dict:
    total = mapped = None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if " in total " in line:
            total = int(line.split()[0])
        if " mapped (" in line and "primary mapped" not in line:
            mapped = int(line.split()[0])
    rate = mapped / total * 100 if mapped is not None and total else None
    return {"total_reads": total, "mapped_reads": mapped, "mapping_rate": rate}


def parse_coverage(path: str | Path) -> float | None:
    with Path(path).open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if not rows:
        return None
    total = next((row for row in rows if row.get("chrom") == "total"), rows[-1])
    return float(total["mean"])


def small_truth_score(calls: list[dict], truth_path: str | None) -> dict | None:
    if not truth_path or not Path(truth_path).exists():
        return None
    truth = parse_vcf(truth_path)
    call_keys = {(row["chrom"], row["pos"], row["ref"], row["alt"]) for row in calls}
    truth_keys = {(row["chrom"], row["pos"], row["ref"], row["alt"]) for row in truth}
    matched = len(call_keys & truth_keys)
    return {
        "truth": len(truth_keys),
        "matched": matched,
        "recall": matched / len(truth_keys) if truth_keys else None,
    }


def reciprocal_overlap(left: dict, right: dict) -> float:
    overlap = max(0, min(left["end"], right["end"]) - max(left["pos"], right["pos"]) + 1)
    if not overlap:
        return 0.0
    left_length = max(1, left["end"] - left["pos"] + 1)
    right_length = max(1, right["end"] - right["pos"] + 1)
    return min(overlap / left_length, overlap / right_length)


def sv_truth_score(calls: list[dict], truth_path: str | None) -> dict | None:
    if not truth_path or not Path(truth_path).exists():
        return None
    truth = parse_vcf(truth_path)
    matched = 0
    for truth_record in truth:
        if any(
            call["chrom"] == truth_record["chrom"]
            and call["type"] == truth_record["type"]
            and reciprocal_overlap(call, truth_record) >= 0.5
            for call in calls
        ):
            matched += 1
    return {
        "truth": len(truth),
        "matched": matched,
        "recall": matched / len(truth) if truth else None,
    }


def write_variant_table(path: str | Path, records: list[dict]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ("chrom", "pos", "end", "id", "ref", "alt", "qual", "filter", "type", "info")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def metric(value, suffix: str = "") -> str:
    if value is None:
        return "NA"
    if isinstance(value, float):
        return f"{value:.2f}{suffix}"
    return f"{value}{suffix}"


def dashboard(project: str, samples: list[dict]) -> str:
    cards = []
    sample_rows = []
    variant_types: Counter[str] = Counter()
    for sample in samples:
        variant_types.update(sample["small_types"])
        variant_types.update(sample["sv_types"])
        cards.extend(
            (
                (f"{sample['sample']} depth", metric(sample["mean_depth"], "×")),
                (f"{sample['sample']} mapped", metric(sample["mapping_rate"], "%")),
                (f"{sample['sample']} small variants", str(sample["small_variants"])),
                (f"{sample['sample']} SVs", str(sample["structural_variants"])),
            )
        )
        small_recall = sample.get("small_truth") or {}
        sv_recall = sample.get("sv_truth") or {}
        sample_rows.append(
            "<tr>"
            f"<td>{html.escape(sample['sample'])}</td>"
            f"<td>{metric(sample['mean_depth'])}</td>"
            f"<td>{metric(sample['mapping_rate'])}</td>"
            f"<td>{sample['small_variants']}</td>"
            f"<td>{sample['structural_variants']}</td>"
            f"<td>{metric(small_recall.get('recall', None) * 100 if small_recall.get('recall') is not None else None, '%')}</td>"
            f"<td>{metric(sv_recall.get('recall', None) * 100 if sv_recall.get('recall') is not None else None, '%')}</td>"
            "</tr>"
        )

    card_html = "".join(
        f'<article class="card"><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong></article>'
        for label, value in cards
    )
    max_count = max(variant_types.values(), default=1)
    bars = "".join(
        f'<div class="bar-row"><span>{html.escape(kind)}</span><div class="track"><div class="fill" style="width:{count / max_count * 100:.1f}%"></div></div><b>{count}</b></div>'
        for kind, count in sorted(variant_types.items())
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(project)} — WGSFlow</title>
<style>
:root {{ color-scheme: light dark; --accent:#13a89e; --panel:#ffffff; --bg:#f2f6f7; --ink:#173238; }}
@media (prefers-color-scheme: dark) {{ :root {{ --panel:#142226; --bg:#0c1518; --ink:#edf8f8; }} }}
* {{ box-sizing:border-box; }} body {{ margin:0; font-family:Inter,system-ui,sans-serif; background:var(--bg); color:var(--ink); }}
main {{ max-width:1180px; margin:auto; padding:2rem; }} h1 {{ margin-bottom:.25rem; }} .subtitle {{ opacity:.7; margin-top:0; }}
.cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:1rem; }}
.card, section {{ background:var(--panel); border-radius:16px; padding:1.2rem; box-shadow:0 8px 30px rgba(0,0,0,.08); }}
.card span {{ display:block; opacity:.7; font-size:.86rem; }} .card strong {{ display:block; font-size:1.55rem; margin-top:.4rem; }}
section {{ margin-top:1.2rem; overflow:auto; }} table {{ border-collapse:collapse; width:100%; }} th,td {{ padding:.7rem; border-bottom:1px solid rgba(120,140,145,.25); text-align:left; }}
.bar-row {{ display:grid; grid-template-columns:90px 1fr 60px; gap:.8rem; align-items:center; margin:.8rem 0; }} .track {{ height:12px; border-radius:10px; background:rgba(100,130,135,.2); overflow:hidden; }} .fill {{ height:100%; background:var(--accent); }}
a {{ color:var(--accent); font-weight:650; }} .warning {{ border-left:5px solid #d98d00; }}
</style>
</head>
<body><main>
<h1>🧬 {html.escape(project)}</h1><p class="subtitle">WGSFlow execution dashboard</p>
<div class="cards">{card_html}</div>
<section><h2>Sample summary</h2><table><thead><tr><th>Sample</th><th>Mean depth</th><th>Mapped %</th><th>Small variants</th><th>SVs</th><th>Small truth recall</th><th>SV truth recall</th></tr></thead><tbody>{''.join(sample_rows)}</tbody></table></section>
<section><h2>Variant classes</h2>{bars or '<p>No calls emitted.</p>'}</section>
<section><h2>Reports and tables</h2><p><a href="../qc/multiqc/multiqc_report.html">Open MultiQC</a> · <a href="snakemake-report.html">Open Snakemake provenance report</a> · <a href="../tables/">Variant tables</a></p></section>
<section class="warning"><strong>Research use only.</strong> Verify reference build, sample identity, coverage, contamination, ploidy, caller assumptions, filters, and truth-set compatibility before interpreting real human data.</section>
</main></body></html>"""


Path(snakemake.log[0]).parent.mkdir(parents=True, exist_ok=True)
Path(snakemake.output.json).parent.mkdir(parents=True, exist_ok=True)

samples = []
for index, sample_name in enumerate(list(snakemake.params.samples)):
    small_calls = parse_vcf(snakemake.input.small[index])
    sv_calls = parse_vcf(snakemake.input.sv[index])
    write_variant_table(snakemake.output.small_tables[index], small_calls)
    write_variant_table(snakemake.output.sv_tables[index], sv_calls)

    alignment = parse_flagstat(snakemake.input.flagstat[index])
    sample = {
        "sample": sample_name,
        "mean_depth": parse_coverage(snakemake.input.coverage[index]),
        **alignment,
        "small_variants": len(small_calls),
        "structural_variants": len(sv_calls),
        "small_types": dict(Counter(row["type"] for row in small_calls)),
        "sv_types": dict(Counter(row["type"] for row in sv_calls)),
        "small_truth": small_truth_score(small_calls, snakemake.params.small_truth),
        "sv_truth": sv_truth_score(sv_calls, snakemake.params.sv_truth),
    }
    samples.append(sample)

payload = {"project": str(snakemake.params.project), "samples": samples}
Path(snakemake.output.json).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

with Path(snakemake.output.tsv).open("w", encoding="utf-8", newline="") as handle:
    writer = csv.writer(handle, delimiter="\t")
    writer.writerow(("sample", "mean_depth", "mapping_rate", "small_variants", "structural_variants", "small_truth_recall", "sv_truth_recall"))
    for sample in samples:
        writer.writerow(
            (
                sample["sample"],
                sample["mean_depth"],
                sample["mapping_rate"],
                sample["small_variants"],
                sample["structural_variants"],
                (sample.get("small_truth") or {}).get("recall"),
                (sample.get("sv_truth") or {}).get("recall"),
            )
        )

Path(snakemake.output.html).write_text(
    dashboard(str(snakemake.params.project), samples), encoding="utf-8"
)
Path(snakemake.log[0]).write_text(f"Summarized {len(samples)} sample(s).\n", encoding="utf-8")
