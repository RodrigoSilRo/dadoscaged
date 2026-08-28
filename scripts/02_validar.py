# -*- coding: utf-8 -*-
"""Passo 2 — reconfere um CSV já gerado contra o painel, a qualquer momento.

Roda de forma independente da extração: lê o arquivo do disco e consulta o
painel de novo. Serve para (a) auditar um arquivo recebido de terceiros e
(b) detectar que o órgão revisou a série desde a coleta.

    python scripts/02_validar.py data/processed/caged_comercio_subclasse_mensal.csv
"""
import argparse
import csv
import json
import os

import _caminho
from dadoscaged import config, validate


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("csv", help="arquivo a conferir")
    p.add_argument("--setor", default=None,
                   help="setor do arquivo (padrão: lê do manifesto, ou 'Comércio')")
    args = p.parse_args()

    setor = args.setor
    manifesto = os.path.splitext(args.csv)[0] + ".manifesto.json"
    if setor is None and os.path.exists(manifesto):
        with open(manifesto, encoding="utf-8") as f:
            m = json.load(f)
        setor = m.get("setor")
        print("manifesto: coletado em %s, refresh do painel %s"
              % (m.get("coletado_em_utc"), m.get("ultimo_refresh_do_painel")))
    setor = setor or "Comércio"
    if setor == "todos":
        setor = None

    with open(args.csv, encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f, delimiter=";")
        cabecalho = next(r)
        linhas = list(r)

    medidas = [m for m in config.MEDIDAS_PADRAO if m.lower() in cabecalho]
    print("arquivo  : %s (%d linhas)\n" % (args.csv, len(linhas)))
    rel = validate.conferir(cabecalho, linhas, grande_grupamento=setor, medidas=medidas)
    validate.imprimir(rel)
    return 0 if rel["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
