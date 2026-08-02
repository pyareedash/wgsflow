rule prepare_reference:
    input:
        REFERENCE_SOURCE,
    output:
        reference=f"{OUT}/reference/reference.fa",
        fai=f"{OUT}/reference/reference.fa.fai",
        amb=f"{OUT}/reference/reference.fa.amb",
        ann=f"{OUT}/reference/reference.fa.ann",
        bwt=f"{OUT}/reference/reference.fa.bwt.2bit.64",
        pac=f"{OUT}/reference/reference.fa.pac",
        sa=f"{OUT}/reference/reference.fa.0123",
    threads: 4
    log:
        f"{LOG_ROOT}/reference/prepare.log",
    shell:
        r"""
        set -euo pipefail
        mkdir -p "$(dirname {output.reference:q})" "$(dirname {log:q})"
        cp {input:q} {output.reference:q}
        samtools faidx {output.reference:q} > {log:q} 2>&1
        bwa-mem2 index {output.reference:q} >> {log:q} 2>&1
        """


rule align_and_mark_duplicates:
    input:
        r1=f"{OUT}/trimmed/{{sample}}_R1.fastq.gz",
        r2=f"{OUT}/trimmed/{{sample}}_R2.fastq.gz",
        reference=f"{OUT}/reference/reference.fa",
        fai=f"{OUT}/reference/reference.fa.fai",
        amb=f"{OUT}/reference/reference.fa.amb",
        ann=f"{OUT}/reference/reference.fa.ann",
        bwt=f"{OUT}/reference/reference.fa.bwt.2bit.64",
        pac=f"{OUT}/reference/reference.fa.pac",
        sa=f"{OUT}/reference/reference.fa.0123",
    output:
        bam=f"{OUT}/alignment/{{sample}}.markdup.bam",
        bai=f"{OUT}/alignment/{{sample}}.markdup.bam.bai",
    params:
        platform=config.get("alignment", {}).get("platform", "ILLUMINA"),
        alignment_dir=f"{OUT}/alignment",
    threads: 8
    log:
        f"{LOG_ROOT}/alignment/{{sample}}.log",
    shell:
        r"""
        set -euo pipefail
        mkdir -p {params.alignment_dir:q} "$(dirname {log:q})"
        tmp=$(mktemp -d {params.alignment_dir:q}/{wildcards.sample}.tmp.XXXXXX)
        trap 'rm -rf "$tmp"' EXIT

        bwa-mem2 mem \
          -t {threads} \
          -R '@RG\tID:{wildcards.sample}\tSM:{wildcards.sample}\tPL:{params.platform}' \
          {input.reference:q} {input.r1:q} {input.r2:q} 2> {log:q} \
        | samtools view -u - 2>> {log:q} \
        | samtools sort -n -@ {threads} -o "$tmp/name.bam" - 2>> {log:q}

        samtools fixmate -m -@ {threads} "$tmp/name.bam" "$tmp/fixmate.bam" 2>> {log:q}
        samtools sort -@ {threads} -o "$tmp/position.bam" "$tmp/fixmate.bam" 2>> {log:q}
        samtools markdup -r -@ {threads} "$tmp/position.bam" {output.bam:q} 2>> {log:q}
        samtools index -@ {threads} {output.bam:q} {output.bai:q} 2>> {log:q}
        """
