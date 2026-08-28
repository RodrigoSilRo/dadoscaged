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
from dadoscaged import config, extract, validate


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("csv", help="arquivo a conferir")
    p.add_argument("--setor", default=None,
                   help="setor do arquivo (padrão: lê do manifesto, ou 'Comércio')")
    args = p.parse_args()

    setor = args.setor
    nivel = "CNAE 2.0 Subclasse"
    caminho_manifesto = os.path.splitext(args.csv)[0] + ".manifesto.json"
    if os.path.exists(caminho_manifesto):
        with open(caminho_manifesto, encoding="utf-8") as f:
            man = json.load(f)
        setor = setor or man.get("setor")
        nivel = man.get("nivel", nivel)
        dig = man.get("impressao_digital_dos_dados") or {}
        print("manifesto: coletado em %s" % man.get("coletado_em_utc"))
        print("           versao da fonte na coleta: %s competencias ate %s, sha256 %s"
              % (dig.get("competencias"), dig.get("ultima_competencia"),
                 (dig.get("sha256_dos_totais") or "?")[:16]))
        print("           (refresh declarado pelo painel, nao confiavel: %s)"
              % man.get("ultimo_refresh_declarado"))
    setor = setor or "Comércio"
    if setor == "todos":
        setor = None

    with open(args.csv, encoding="utf-8-sig", newline="") as f:
        r = csv.reader(f, delimiter=";")
        cabecalho = next(r)
        linhas = list(r)

    conhecidas = config.MEDIDAS_ADITIVAS + config.MEDIDAS_COMPOSTAS
    medidas = [m for m in conhecidas if extract._rotulo(m) in cabecalho]
    print("arquivo  : %s (%d linhas)" % (args.csv, len(linhas)))
    print("nivel    : %s\n" % nivel)
    rel = validate.conferir(cabecalho, linhas, grande_grupamento=setor, medidas=medidas,
                            nivel=nivel)
    validate.imprimir(rel)
    return 0 if rel["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
