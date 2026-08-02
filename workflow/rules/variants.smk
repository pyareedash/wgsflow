rule call_small_variants:
    input:
        reference=f"{OUT}/reference/reference.fa",
        fai=f"{OUT}/reference/reference.fa.fai",
        bam=f"{OUT}/alignment/{{sample}}.markdup.bam",
        bai=f"{OUT}/alignment/{{sample}}.markdup.bam.bai",
    output:
        vcf=f"{OUT}/variants/{{sample}}.small.vcf.gz",
        index=f"{OUT}/variants/{{sample}}.small.vcf.gz.tbi",
        stats=f"{OUT}/qc/variants/{{sample}}.small.stats.txt",
    params:
        min_mq=config.get("small_variants", {}).get("min_mapping_quality", 20),
        min_bq=config.get("small_variants", {}).get("min_base_quality", 20),
        min_qual=config.get("small_variants", {}).get("min_quality", 20),
    threads: 4
    log:
        f"{LOG_ROOT}/variants/{{sample}}.small.log",
    shell:
        r"""
        set -euo pipefail
        mkdir -p "$(dirname {output.vcf:q})" "$(dirname {output.stats:q})" \
          "$(dirname {log:q})"
        bcftools mpileup \
          --threads {threads} \
          --fasta-ref {input.reference:q} \
          --min-MQ {params.min_mq} \
          --min-BQ {params.min_bq} \
          --annotate FORMAT/DP,FORMAT/AD \
          --output-type u {input.bam:q} 2> {log:q} \
        | bcftools call \
          --threads {threads} --multiallelic-caller --variants-only \
          --output-type u 2>> {log:q} \
        | bcftools norm \
          --threads {threads} --fasta-ref {input.reference:q} \
          --multiallelics -any --output-type u 2>> {log:q} \
        | bcftools filter \
          --threads {threads} --soft-filter LowQual \
          --exclude 'QUAL<{params.min_qual}' \
          --output-type z --output {output.vcf:q} 2>> {log:q}

        bcftools index --tbi {output.vcf:q} 2>> {log:q}
        bcftools stats {output.vcf:q} > {output.stats:q} 2>> {log:q}
        """


rule call_structural_variants:
    input:
        reference=f"{OUT}/reference/reference.fa",
        fai=f"{OUT}/reference/reference.fa.fai",
        bam=f"{OUT}/alignment/{{sample}}.markdup.bam",
        bai=f"{OUT}/alignment/{{sample}}.markdup.bam.bai",
    output:
        vcf=f"{OUT}/variants/{{sample}}.sv.vcf.gz",
        index=f"{OUT}/variants/{{sample}}.sv.vcf.gz.tbi",
        stats=f"{OUT}/qc/variants/{{sample}}.sv.stats.txt",
    params:
        min_qual=config.get("structural_variants", {}).get("min_quality", 20),
        variants_dir=f"{OUT}/variants",
    threads: 4
    log:
        f"{LOG_ROOT}/variants/{{sample}}.sv.log",
    shell:
        r"""
        set -euo pipefail
        mkdir -p {params.variants_dir:q} "$(dirname {output.stats:q})" \
          "$(dirname {log:q})"
        raw=$(mktemp --suffix=.bcf {params.variants_dir:q}/{wildcards.sample}.delly.XXXXXX)
        trap 'rm -f "$raw" "$raw.csi"' EXIT

        OMP_NUM_THREADS={threads} delly call -g {input.reference:q} -o "$raw" \
          {input.bam:q} > {log:q} 2>&1
        bcftools view --threads {threads} --output-type u "$raw" 2>> {log:q} \
        | bcftools filter \
          --threads {threads} --soft-filter LowQual \
          --exclude 'QUAL<{params.min_qual}' \
          --output-type z --output {output.vcf:q} 2>> {log:q}

        bcftools index --tbi {output.vcf:q} 2>> {log:q}
        bcftools stats {output.vcf:q} > {output.stats:q} 2>> {log:q}
        """
