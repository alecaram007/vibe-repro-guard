# Vibe Repro Guard

Skill operativa per aumentare la riproducibilità nel vibe coding con AI, tramite replay deterministico locale.

## Quando usarla
- Quando vuoi verificare che una modifica AI sia ripetibile su macchina pulita.
- Prima di aprire PR, tagliare release o consegnare a un altro dev.
- Quando i test passano "a volte sì, a volte no" e vuoi evidenze concrete.

## Workflow (4 fasi)
1. `baseline`: fingerprint ambiente e toolchain.
2. `contract`: validazione del contratto di riproducibilità da `reproguard.yaml`.
3. `replay`: esecuzione build/test in workspace temporaneo pulito.
4. `report`: score 0-100, issue prioritarie, remediation.

## Setup rapido (zero config)
```bash
reproguard init   # scansiona il progetto e genera reproguard.yaml
reproguard         # esegue il guard
```

`init` rileva: project type (Python/Node/PHP/Rust/Go/Ruby), runtime locale, lockfile presenti, env vars referenziate nel codice.

## Setup manuale (se preferisci)
1. Copia `reproguard.yaml.example` in `reproguard.yaml`.
2. Imposta `build_command`, `test_command`, `runtime`, `required_env` e `lockfiles`.
3. Esegui:

```bash
./reproguard.sh
```

## CI / pre-commit
- **GitHub Action**: `uses: alecaram007/vibe-repro-guard@v1`
- **pre-commit**: hook `reproguard` registrato nel manifest `.pre-commit-hooks.yaml`
- **Altri CI** (GitLab, Circle, Buildkite, Jenkins): snippet pronti in [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md)
- **SARIF**: `reproguard --sarif` produce `reproguard.report.sarif.json` per GitHub Code Scanning

## Debug
- `reproguard --version` — versione installata
- `reproguard doctor` — diagnostico ambiente (Python/git/toolchain/config)
- `reproguard explain <issue_id>` — spiegazione completa di un issue trovato nel report
- `reproguard explain --list` — elenco di tutti gli issue ID noti
- `reproguard --phase baseline|contract|replay` — esegui solo fino a una fase (debug pipeline)

## Output
Artefatti generati nella root del progetto:
- `reproguard.contract.json`
- `reproguard.report.json`
- `reproguard.report.md`

Exit codes:
- `0`: replay OK e policy rispettata
- `20`: replay fallito
- `30`: score sotto soglia in `strict`
- `40`: configurazione invalida
- `41`: precondizione `init` non soddisfatta (config già esistente senza `--force`)

## Modalità
- `advisory` (default): segnala rischi senza bloccare per score.
- `strict`: fallisce se `score < score_threshold`.

## Hardening v1.1
- `replay_runs` (2-10): riesegue i test più volte e verifica stabilità di exit code e output hash.
- `fail_on_lockfile_drift`: se `true`, il replay fallisce quando un lockfile viene creato/modificato/cancellato durante la verifica.
- `redact_env_patterns`: maschera valori sensibili nei log salvati in report (`[REDACTED]`).
- `require_declared_env_values`: se `true`, segnala e penalizza quando variabili in `required_env` non sono esportate.

## Linguaggi supportati
Project type e lockfile inferiti automaticamente da:
- Python (`pyproject.toml`, `requirements.txt`, `setup.py`)
- Node (`package.json`)
- PHP (`composer.json`)
- Rust (`Cargo.toml`)
- Go (`go.mod`)
- Ruby (`Gemfile`)

Scansione env/non-determinismo: `.py .js .ts .tsx .jsx .mjs .cjs .rs .go .rb`.

Zero-test detection: unittest, pytest, jest, vitest, mocha, `go test`, `cargo test`, rspec, phpunit.

## Note operative
- Nessuna dipendenza extra Python richiesta.
- Target v1: macOS/Linux, workflow terminale locale.
- Heuristics incluse: lockfile mancante, runtime non pin-nato/drift, env implicite, segnali di non-determinismo nei test.
