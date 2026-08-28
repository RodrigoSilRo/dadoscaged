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
    # A extração emite uma consulta por ano. Se as respostas vierem de versões
    # diferentes da série, o arquivo sai internamente inconsistente — sem nada
    # que denuncie o problema depois. Isso não é hipotético: durante uma
    # atualização, o backend responde requisições consecutivas a partir de
    # réplicas em estados diferentes (ver docs/LIMITACOES.md, seção 2).
    print("\nVerificando se a fonte esta servindo uma unica versao...")
    estavel, amostras = extract.conferir_replicas(setor)
    for a in amostras:
        print("   %s competencias ate %s, sha256 %s"
              % (a["competencias"], a["ultima_competencia"], a["sha256_dos_totais"][:16]))
    if not estavel:
        print("\n  AVISO: a fonte respondeu com versoes DIFERENTES da serie em")
        print("  requisicoes consecutivas — atualizacao em propagacao. A extracao")
        print("  continua, mas so sera gravada se passar na validacao completa,")
        print("  que confere cada mes contra uma consulta nova ao painel.")

    digital_antes = amostras[0]
    print("\nVersao dos dados: %s competencias (%s a %s), sha256 %s"
          % (digital_antes["competencias"], digital_antes["primeira_competencia"],
             digital_antes["ultima_competencia"], digital_antes["sha256_dos_totais"][:16]))

    # O painel pode servir uma competencia que ainda nao consta da sua capa —
    # dados carregados antes da divulgacao oficial. Foi observado na pratica
    # (ver docs/LIMITACOES.md, secao 1). Nao e motivo para abortar, mas tem de
    # ficar registrado: os numeros dessa competencia podem ser retirados depois.
    mes_declarado = extract.mes_de_referencia_declarado()
    ultima = digital_antes["ultima_competencia"]
    if mes_declarado and ultima and ultima > mes_declarado:
        print("\n  ATENCAO: o painel serve ate %s, mas a capa declara %s como"
              " mes de referencia." % (ultima, mes_declarado))
        print("  A competencia %s pode nao estar oficialmente divulgada." % ultima)

    print("\nExtraindo...")
    cabecalho, linhas = extract.extrair(
        nivel=args.nivel, grande_grupamento=setor, anos=args.anos, medidas=medidas,
        dir_raw=None if args.sem_raw else _caminho.DIR_RAW)

    # Identidade calculada sobre as proprias linhas: descreve o arquivo, nao o
    # que uma consulta extra por acaso devolveria.
    digital_arquivo = extract.digital_dos_dados(cabecalho, linhas, medidas)
    coincide = digital_arquivo["sha256_dos_totais"] == digital_antes["sha256_dos_totais"]
    print("\nIdentidade do arquivo: %s competencias (%s a %s), sha256 %s"
          % (digital_arquivo["competencias"], digital_arquivo["primeira_competencia"],
             digital_arquivo["ultima_competencia"],
             digital_arquivo["sha256_dos_totais"][:16]))
    if not coincide:
        print("  (difere da amostra tirada antes da extracao — a fonte mudou no"
              " intervalo)")

    # O portao duro nao e a impressao digital: e a validacao completa, que
    # confere CADA mes contra consultas novas ao painel. Um arquivo que misture
    # versoes falha ali, porque os totais nao fecham.
    print("\nValidando contra os totais do painel...")
    rel = validate.conferir(cabecalho, linhas, grande_grupamento=setor, medidas=medidas,
                            nivel=args.nivel)
    validate.imprimir(rel)
    if not rel["ok"]:
        print("\nExtracao NAO gravada: a conferencia contra o painel acusou divergencia.")
        return 1

    with open(saida, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(cabecalho)
        w.writerows(linhas)
    print("\ngravado: %s" % saida)

    # Manifesto de proveniência do arquivo gerado.
    # A identidade gravada é calculada sobre as linhas do arquivo, não por uma
    # consulta nova: assim ela descreve o que está no disco, sempre.
    manifesto = extract.carimbo_execucao(setor, digital=digital_arquivo)
    manifesto.update({
        "fonte_servia_versao_unica_no_inicio": estavel,
        "amostras_da_fonte_antes_da_coleta": amostras,
        "identidade_do_arquivo_coincide_com_amostra_inicial": coincide,
        "mes_de_referencia_declarado_na_capa": mes_declarado,
        "ultima_competencia_no_arquivo": digital_arquivo["ultima_competencia"],
        "arquivo": os.path.basename(saida),
        "sha256": sha256(saida),
        "linhas": len(linhas),
        "colunas": cabecalho,
        "setor": setor or "todos",
        "nivel": args.nivel,
        "medidas": medidas,
        "anos": args.anos or extract.listar_anos(),
        "validacao": {
            "medidas_aditivas": rel["medidas_aditivas"],
            "medidas_compostas": rel["medidas_compostas"],
            "soma_x_total": {"meses_conferidos": rel["soma"]["meses_no_painel"],
                             "divergencias": len(rel["soma"]["divergencias"])},
            "nivel_pai": {
                "nivel": rel["soma"]["checagem_nivel_pai"]["nivel"],
                "divergencias": len(rel["soma"]["checagem_nivel_pai"]["divergencias"])},
            "residuos_da_fonte": rel["soma"]["residuos"],
            "celula_a_celula": {"competencias": rel["celula"]["competencias_sorteadas"],
                                "celulas_conferidas": rel["celula"]["celulas_conferidas"],
                                "divergencias": len(rel["celula"]["divergencias"])},
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
