# Public datasets

## 1. Synthetic truth dataset

Use this for every clean installation and pull request. It is deterministic, small, and contains known SNP, small-deletion, and structural-deletion events.

```bash
pixi run wgsflow data synthetic --force
pixi run wgsflow run --config config/demo.yaml --cores 4
```

## 2. Google's NA12878 chromosome 20 quick-start bundle

The command downloads Google's public DeepVariant tutorial BAM/reference/truth files and reconstructs paired FASTQs so WGSFlow still starts from FASTQ.

```bash
pixi run wgsflow data quickstart --force
pixi run wgsflow run --config config/quickstart.yaml --cores 4
```


## 3. GIAB HG002


1. Start with chromosome 20 at approximately 30× coverage.
2. Use a reference and truth set with exactly matching contig names and build.
3. Progress to full WGS only after regional runs are stable.

GIAB data are distributed by NIST and through the AWS Registry of Open Data. Do not mix GRCh37, GRCh38, and T2T truth resources.

## 4. Diverse-data progression

A useful test matrix is:

| Stage | Data | Purpose |
|---|---|---|
| CI | Synthetic | deterministic workflow behavior |
| Real tiny | NA12878 chr20 tutorial region | real FASTQ/alignment/calling integration |
| Full WGS | HG002 30× | performance, storage, scaling, and complete QC |
| Additional samples | HG001/HG003/HG004 | robustness across libraries and individuals |
