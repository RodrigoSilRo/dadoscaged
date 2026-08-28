# -*- coding: utf-8 -*-
"""Passo 1 — extrai a série mensal de um setor no nível pedido.

Exemplos:
    python scripts/01_extrair.py
    python scripts/01_extrair.py --setor Serviços --nivel "CNAE 2.0 Classe"
    python scripts/01_extrair.py --setor Comércio --anos 2024 2025 2026

A extração falha (código de saída 1) se a validação contra os totais do painel
não bater. Um arquivo em data/processed/ só existe se tiver passado na
conferência.
"""
import argparse
import csv
import hashlib
import json
import os
from datetime import datetime, timezone

import _caminho
from dadoscaged import config, extract, validate


def sha256(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--setor", default="Comércio",
                   help="valor de 'Grande Grupamento'; use 'todos' para não filtrar")
    p.add_argument("--nivel", default="CNAE 2.0 Subclasse",
                   choices=config.HIERARQUIA_SETORIAL,
                   help="nível de desagregação da saída")
    p.add_argument("--anos", nargs="*", default=None,
                   help="anos a extrair (padrão: todos os disponíveis)")
    p.add_argument("--medidas", nargs="*", default=None,
                   help="medidas (padrão: %s)" % ", ".join(config.MEDIDAS_PADRAO))
    p.add_argument("--saida", default=None, help="caminho do CSV de saída")
    p.add_argument("--sem-raw", action="store_true",
                   help="não arquivar as respostas brutas da API")
    args = p.parse_args()

    setor = None if args.setor.lower() == "todos" else args.setor
    medidas = args.medidas or list(config.MEDIDAS_PADRAO)

    os.makedirs(_caminho.DIR_PROC, exist_ok=True)
    saida = args.saida or os.path.join(
        _caminho.DIR_PROC,
        "caged_%s_%s_mensal.csv" % (extract._rotulo(setor or "todos"),
                                    extract._rotulo(args.nivel)))

    print("Fonte : %s" % config.PAINEL_URL)
    print("Setor : %s" % (setor or "todos"))
    print("Nivel : %s" % args.nivel)
    print("\nExtraindo...")
    cabecalho, linhas = extract.extrair(
        nivel=args.nivel, grande_grupamento=setor, anos=args.anos, medidas=medidas,
        dir_raw=None if args.sem_raw else _caminho.DIR_RAW)

    print("\nValidando contra os totais do painel...")
    rel = validate.conferir(cabecalho, linhas, grande_grupamento=setor, medidas=medidas)
    validate.imprimir(rel)
    if not rel["ok"]:
        print("\nExtracao NAO gravada: a soma dos niveis desagregados nao reproduz "
              "o total do painel.")
        return 1

    with open(saida, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(cabecalho)
        w.writerows(linhas)
    print("\ngravado: %s" % saida)

    # Manifesto de proveniência do arquivo gerado.
    manifesto = extract.carimbo_execucao()
    manifesto.update({
        "arquivo": os.path.basename(saida),
        "sha256": sha256(saida),
        "linhas": len(linhas),
        "colunas": cabecalho,
        "setor": setor or "todos",
        "nivel": args.nivel,
        "medidas": medidas,
        "anos": args.anos or extract.listar_anos(),
        "validacao": {"meses_conferidos": rel["meses_no_painel"],
                      "divergencias": len(rel["divergencias"]),
                      "ok": rel["ok"]},
        "gerado_por": "scripts/01_extrair.py",
        "gerado_em_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })
    cam_man = os.path.splitext(saida)[0] + ".manifesto.json"
    with open(cam_man, "w", encoding="utf-8") as f:
        json.dump(manifesto, f, ensure_ascii=False, indent=1)
    print("gravado: %s" % cam_man)
    print("sha256 : %s" % manifesto["sha256"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
