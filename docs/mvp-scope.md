# MVP engineering decisions

## Reliability choices

- One Pixi environment instead of per-rule solver fan-out.
- Native Snakemake console logging instead of a custom logger plugin.
- No workflow hooks; email is sent after the Snakemake subprocess exits.
- Standard local executor only.
- Established Bioconda tools with broad compatible version ranges.
- Plain TSV/JSON/HTML outputs with no application server dependency.
- A dashboard failure cannot invalidate completed variant calls.

## Upgrade path after the MVP passes diverse datasets

1. Freeze and commit `pixi.lock`.
2. Add DeepVariant as an explicitly optional container-backed caller.
3. Add VEP offline annotation as an optional target.
4. Add one tested cluster profile.
5. Add a genome browser only after data contracts are stable.

Each capability should arrive behind an explicit config flag and its own integration test.
