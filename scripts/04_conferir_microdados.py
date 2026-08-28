# -*- coding: utf-8 -*-
"""Passo 4 (opcional) — confere o painel contra os microdados oficiais do FTP.

Esta é a validação mais forte disponível: em vez de comparar o painel consigo
mesmo, reconstrói uma competência a partir dos registros individuais publicados
pelo MTE e verifica se o agregado bate.

Os microdados são organizados por **competência de declaração**; o painel, por
**competência de movimentação**. Um mês do painel é, portanto:

    MOV_m  +  soma sobre d > m de (FOR_d - EXC_d) restritos a compmov = m

onde `FOR` são declarações fora do prazo e `EXC`, exclusões. É por isso que o
valor de um mês muda depois de publicado — e é isso que este script mede.

    python scripts/04_conferir_microdados.py --competencia 202203 --revisoes 9

Requer `py7zr` (pip install py7zr) e acesso ao FTP do MTE. Baixa ~55 MB para a
competência-base e ~1 MB por mês de revisão.
"""
import argparse
import collections
import csv
import io
import os
import shutil
import urllib.request

import _caminho
from dadoscaged import config

FTP = "ftp://ftp.mtps.gov.br/pdet/microdados/NOVO%20CAGED"
# "Comércio" no agrupamento do MTE corresponde exatamente à seção G da CNAE 2.0.
SECAO_DE = {"Comércio": "G", "Indústria": None, "Construção": "F",
            "Agropecuária": "A", "Serviços": None}


def competencias_seguintes(comp, n):
    ano, mes = divmod(int(comp), 100)
    saida = []
    for _ in range(n):
        mes += 1
        if mes > 12:
            ano, mes = ano + 1, 1
        saida.append("%04d%02d" % (ano, mes))
    return saida


def baixar(nome, comp, destino):
    caminho = os.path.join(destino, nome)
    if os.path.exists(caminho):
        return caminho
    url = "%s/%s/%s/%s" % (FTP, comp[:4], comp, nome)
    try:
        with urllib.request.urlopen(url, timeout=600) as r, open(caminho, "wb") as f:
            shutil.copyfileobj(r, f)
    except Exception as e:
        print("   (indisponivel: %s — %s)" % (nome, e))
        return None
    return caminho


def linhas(caminho_7z, destino):
    import py7zr
    saida = os.path.join(destino, "extraido")
    if os.path.isdir(saida):
        shutil.rmtree(saida)
    os.makedirs(saida)
    with py7zr.SevenZipFile(caminho_7z, "r") as z:
        z.extractall(path=saida)
    for raiz, _, arquivos in os.walk(saida):
        for a in arquivos:
            with io.open(os.path.join(raiz, a), encoding="utf-8", newline="") as f:
                for r in csv.DictReader(f, delimiter=";"):
                    yield r


def contar(iterador, comp, secao):
    adm = des = 0
    for r in iterador:
        if r.get("competênciamov") != comp:
            continue
        if secao and r.get("seção") != secao:
            continue
        if int(r["saldomovimentação"]) > 0:
            adm += 1
        else:
            des += 1
    return adm, des


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--competencia", default="202203", help="competência a reconstruir (AAAAMM)")
    p.add_argument("--revisoes", type=int, default=9,
                   help="quantos meses seguintes de declarações somar")
    p.add_argument("--setor", default="Comércio")
    p.add_argument("--csv", default=None, help="CSV do painel a comparar")
    p.add_argument("--cache", default=None, help="diretório para os arquivos do FTP")
    args = p.parse_args()

    secao = SECAO_DE.get(args.setor)
    if secao is None:
        print("Setor %r nao tem correspondencia direta com uma secao da CNAE." % args.setor)
        print("Setores suportados: %s"
              % ", ".join(k for k, v in SECAO_DE.items() if v))
        return 2

    destino = args.cache or os.path.join(_caminho.DIR_DADOS, "microdados")
    os.makedirs(destino, exist_ok=True)
    comp = args.competencia

    # Valor de referência: o painel, na extração já validada.
    caminho_csv = args.csv or os.path.join(
        _caminho.DIR_PROC, "caged_comercio_subclasse_mensal.csv")
    p_adm = p_des = 0
    with io.open(caminho_csv, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            if r["competencia"] == comp:
                p_adm += int(r["admitidos"])
                p_des += int(r["desligados"])
    if not p_adm:
        print("Competencia %s nao encontrada em %s" % (comp, caminho_csv))
        return 2

    print("Reconstruindo %s (%s = secao %s) a partir dos microdados do FTP\n"
          % (comp, args.setor, secao))

    arq = baixar("CAGEDMOV%s.7z" % comp, comp, destino)
    if not arq:
        return 1
    adm, des = contar(linhas(arq, destino), comp, secao)
    primeiro = (adm, des)
    print("%-46s %9s %9s %9s" % ("acumulado ate", "admitidos", "desligados", "saldo"))
    print("%-46s %9d %9d %+9d" % ("MOV%s (dentro do prazo)" % comp, adm, des, adm - des))

    for m in competencias_seguintes(comp, args.revisoes):
        f_arq = baixar("CAGEDFOR%s.7z" % m, m, destino)
        e_arq = baixar("CAGEDEXC%s.7z" % m, m, destino)
        if not f_arq or not e_arq:
            break
        fa, fd = contar(linhas(f_arq, destino), comp, secao)
        ea, ed = contar(linhas(e_arq, destino), comp, secao)
        adm += fa - ea
        des += fd - ed
        print("%-46s %9d %9d %+9d   (FOR +%d/+%d, EXC -%d/-%d)"
              % ("  + declaracoes de %s" % m, adm, des, adm - des, fa, fd, ea, ed))

    print("\n%-46s %9d %9d %+9d" % ("PAINEL (extracao validada)", p_adm, p_des, p_adm - p_des))
    falta_a, falta_d = p_adm - adm, p_des - des
    print("%-46s %9d %9d" % ("ainda por explicar (declaracoes posteriores)", falta_a, falta_d))
    tot_a, tot_d = p_adm - primeiro[0], p_des - primeiro[1]
    if tot_a and tot_d:
        print("\nrevisao explicada: admitidos %.1f%% | desligados %.1f%%"
              % (100 * (adm - primeiro[0]) / tot_a, 100 * (des - primeiro[1]) / tot_d))
    print("\nO residuo cai para zero somando TODAS as competencias de declaracao\n"
          "posteriores, ate a ultima disponivel. Ver docs/LIMITACOES.md, secao 12.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
