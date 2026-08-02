rule fastqc:
    input:
        r1=read1,
        r2=read2,
    output:
        directory(f"{OUT}/qc/fastqc/{{sample}}"),
    threads: 2
    log:
        f"{LOG_ROOT}/fastqc/{{sample}}.log",
    shell:
        r"""
        set -euo pipefail
        mkdir -p {output:q} "$(dirname {log:q})"
        fastqc --threads {threads} --outdir {output:q} \
          {input.r1:q} {input.r2:q} > {log:q} 2>&1
        """


rule fastp:
    input:
        r1=read1,
        r2=read2,
    output:
        r1=f"{OUT}/trimmed/{{sample}}_R1.fastq.gz",
        r2=f"{OUT}/trimmed/{{sample}}_R2.fastq.gz",
        json=f"{OUT}/qc/fastp/{{sample}}.json",
        html=f"{OUT}/qc/fastp/{{sample}}.html",
    params:
        minimum_length=config.get("preprocessing", {}).get("minimum_length", 50),
        adapter=(
            "--detect_adapter_for_pe"
            if config.get("preprocessing", {}).get("detect_adapter_for_pe", True)
            else ""
        ),
    threads: 4
    log:
        f"{LOG_ROOT}/fastp/{{sample}}.log",
    shell:
        r"""
        set -euo pipefail
        mkdir -p "$(dirname {output.r1:q})" "$(dirname {output.json:q})" \
          "$(dirname {log:q})"
        fastp \
          --in1 {input.r1:q} --in2 {input.r2:q} \
          --out1 {output.r1:q} --out2 {output.r2:q} \
          --json {output.json:q} --html {output.html:q} \
          --thread {threads} --length_required {params.minimum_length} \
          {params.adapter} > {log:q} 2>&1
        """


rule alignment_qc:
    input:
        bam=f"{OUT}/alignment/{{sample}}.markdup.bam",
        bai=f"{OUT}/alignment/{{sample}}.markdup.bam.bai",
    output:
        flagstat=f"{OUT}/qc/alignment/{{sample}}.flagstat.txt",
        stats=f"{OUT}/qc/alignment/{{sample}}.stats.txt",
        coverage=f"{OUT}/qc/coverage/{{sample}}.mosdepth.summary.txt",
        distribution=f"{OUT}/qc/coverage/{{sample}}.mosdepth.global.dist.txt",
    params:
        coverage_prefix=lambda wildcards: f"{OUT}/qc/coverage/{wildcards.sample}",
    threads: 4
    log:
        f"{LOG_ROOT}/alignment_qc/{{sample}}.log",
    shell:
        r"""
        set -euo pipefail
        mkdir -p "$(dirname {output.flagstat:q})" "$(dirname {output.coverage:q})" \
          "$(dirname {log:q})"
        samtools flagstat -@ {threads} {input.bam:q} > {output.flagstat:q} 2> {log:q}
        samtools stats -@ {threads} {input.bam:q} > {output.stats:q} 2>> {log:q}
        mosdepth -n -x -t {threads} {params.coverage_prefix:q} \
          {input.bam:q} >> {log:q} 2>&1
        """
