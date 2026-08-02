rule multiqc:
    input:
        fastqc=expand(f"{OUT}/qc/fastqc/{{sample}}", sample=SAMPLES),
        fastp=expand(f"{OUT}/qc/fastp/{{sample}}.json", sample=SAMPLES),
        flagstat=expand(f"{OUT}/qc/alignment/{{sample}}.flagstat.txt", sample=SAMPLES),
        coverage=expand(f"{OUT}/qc/coverage/{{sample}}.mosdepth.summary.txt", sample=SAMPLES),
        small=expand(f"{OUT}/qc/variants/{{sample}}.small.stats.txt", sample=SAMPLES),
        sv=expand(f"{OUT}/qc/variants/{{sample}}.sv.stats.txt", sample=SAMPLES),
    output:
        f"{OUT}/qc/multiqc/multiqc_report.html",
    params:
        scan_dirs=[
            f"{OUT}/qc/fastqc",
            f"{OUT}/qc/fastp",
            f"{OUT}/qc/alignment",
            f"{OUT}/qc/coverage",
            f"{OUT}/qc/variants",
        ],
        output_dir=f"{OUT}/qc/multiqc",
    log:
        f"{LOG_ROOT}/multiqc/multiqc.log",
    shell:
        r"""
        set -euo pipefail
        mkdir -p {params.output_dir:q} "$(dirname {log:q})"
        multiqc --force --outdir {params.output_dir:q} \
          --filename multiqc_report.html {params.scan_dirs:q} > {log:q} 2>&1
        """


rule summarize:
    input:
        small=expand(f"{OUT}/variants/{{sample}}.small.vcf.gz", sample=SAMPLES),
        sv=expand(f"{OUT}/variants/{{sample}}.sv.vcf.gz", sample=SAMPLES),
        coverage=expand(f"{OUT}/qc/coverage/{{sample}}.mosdepth.summary.txt", sample=SAMPLES),
        flagstat=expand(f"{OUT}/qc/alignment/{{sample}}.flagstat.txt", sample=SAMPLES),
        multiqc=f"{OUT}/qc/multiqc/multiqc_report.html",
    output:
        json=f"{OUT}/report/summary.json",
        tsv=f"{OUT}/report/summary.tsv",
        html=f"{OUT}/report/dashboard.html",
        small_tables=expand(f"{OUT}/tables/{{sample}}.small.tsv", sample=SAMPLES),
        sv_tables=expand(f"{OUT}/tables/{{sample}}.sv.tsv", sample=SAMPLES),
    params:
        samples=SAMPLES,
        project=config.get("project_name", "WGSFlow"),
        small_truth=config.get("truth", {}).get("small_vcf"),
        sv_truth=config.get("truth", {}).get("sv_vcf"),
        out=OUT,
    log:
        f"{LOG_ROOT}/report/summary.log",
    script:
        "../scripts/build_summary.py"
