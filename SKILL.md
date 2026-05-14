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

## Setup rapido
1. Copia `reproguard.yaml.example` in `reproguard.yaml`.
2. Imposta `build_command`, `test_command`, `runtime`, `required_env` e `lockfiles`.
3. Esegui:

```bash
./reproguard.sh
```

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

## Modalità
- `advisory` (default): segnala rischi senza bloccare per score.
- `strict`: fallisce se `score < score_threshold`.

## Hardening v1.1
- `replay_runs` (2-10): riesegue i test più volte e verifica stabilità di exit code e output hash.
- `fail_on_lockfile_drift`: se `true`, il replay fallisce quando un lockfile viene creato/modificato/cancellato durante la verifica.
- `redact_env_patterns`: maschera valori sensibili nei log salvati in report (`[REDACTED]`).
- `require_declared_env_values`: se `true`, segnala e penalizza quando variabili in `required_env` non sono esportate.

## Note operative
- Nessuna dipendenza extra Python richiesta.
- Target v1: macOS/Linux, workflow terminale locale.
- Heuristics incluse: lockfile mancante, runtime non pin-nato/drift, env implicite, segnali di non-determinismo nei test.
