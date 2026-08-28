# -*- coding: utf-8 -*-
"""Testes do decodificador DSR.

O decodificador é o único ponto do pipeline capaz de produzir números errados
sem levantar erro: se a supressão de repetição ou os dicionários de valores
forem mal interpretados, sai uma tabela plausível e incorreta. Os casos abaixo
são recortes reais de respostas do painel.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from dadoscaged import dsr  # noqa: E402


def envelope(ds):
    return {"results": [{"result": {"data": {"dsr": {"DS": [ds]}}}}]}


class TesteDecodificador(unittest.TestCase):

    def test_formato_por_chave(self):
        """Linhas com uma chave por coluna (G0, G1...) e dicionário de valores."""
        ds = {"ValueDicts": {"D0": ["Agropecuária", "Indústria", "Comércio"]},
              "PH": [{"DM0": [{"S": [{"N": "G0", "T": 1, "DN": "D0"}], "G0": 0},
                              {"G0": 1},
                              {"G0": 2}]}]}
        cols, linhas = dsr.decodificar(envelope(ds))
        self.assertEqual(cols, ["G0"])
        self.assertEqual(linhas, [["Agropecuária"], ["Indústria"], ["Comércio"]])

    def test_formato_posicional_com_repeticao(self):
        """Array C + máscara R: o valor omitido repete o da linha anterior."""
        ds = {"ValueDicts": {"D0": ["2020", "2021"], "D1": ["01", "02", "03"]},
              "PH": [{"DM0": [
                  {"S": [{"N": "G0", "T": 1, "DN": "D0"},
                         {"N": "G1", "T": 1, "DN": "D1"},
                         {"N": "G2", "T": 3}],
                   "C": [0, 0, 202001]},
                  {"C": [1, 202002], "R": 1},   # ano repetido
                  {"C": [2, 202003], "R": 1},
                  {"C": [1, 0, 202101]},        # ano muda: nada repetido
              ]}]}
        cols, linhas = dsr.decodificar(envelope(ds))
        self.assertEqual(linhas, [["2020", "01", 202001],
                                  ["2020", "02", 202002],
                                  ["2020", "03", 202003],
                                  ["2021", "01", 202101]])

    def test_repeticao_em_varias_colunas(self):
        """R com vários bits ligados; a ordem posicional de C deve ser respeitada."""
        ds = {"PH": [{"DM0": [
            {"S": [{"N": "G0", "T": 3}, {"N": "G1", "T": 3}, {"N": "M0", "T": 3}],
             "C": [10, 20, 30]},
            {"C": [99], "R": 3},   # bits 0 e 1 repetem; só a medida vem em C
        ]}]}
        _, linhas = dsr.decodificar(envelope(ds))
        self.assertEqual(linhas, [[10, 20, 30], [10, 20, 99]])

    def test_mascara_de_nulos(self):
        """Ø marca coluna nula; o valor NÃO é consumido de C."""
        ds = {"PH": [{"DM0": [
            {"S": [{"N": "G0", "T": 3}, {"N": "M0", "T": 3}], "C": [1, 100]},
            {"C": [2], "\u00d8": 2},   # medida nula
        ]}]}
        _, linhas = dsr.decodificar(envelope(ds))
        self.assertEqual(linhas, [[1, 100], [2, None]])

    def test_nulo_nao_contamina_repeticao(self):
        """Uma coluna nula vira None e é isso que a linha seguinte repete."""
        ds = {"PH": [{"DM0": [
            {"S": [{"N": "G0", "T": 3}, {"N": "M0", "T": 3}], "C": [1, 100]},
            {"C": [2], "\u00d8": 2},
            {"C": [3], "R": 2},
        ]}]}
        _, linhas = dsr.decodificar(envelope(ds))
        self.assertEqual(linhas, [[1, 100], [2, None], [3, None]])

    def test_resposta_sem_dsr(self):
        with self.assertRaises(dsr.ErroDSR):
            dsr.decodificar({"results": [{"result": {}}]})

    def test_linha_truncada(self):
        ds = {"PH": [{"DM0": [
            {"S": [{"N": "G0", "T": 3}, {"N": "G1", "T": 3}], "C": [1]},
        ]}]}
        with self.assertRaises(dsr.ErroDSR):
            dsr.decodificar(envelope(ds))


class TesteConsultas(unittest.TestCase):
    """Garante que o JSON enviado ao painel tem a forma esperada."""

    def test_filtro_escapa_aspas(self):
        from dadoscaged import query
        f = query.filtro_em("e", "Grande Grupamento", ["O'Brien"])
        valor = f[0]["Condition"]["In"]["Values"][0][0]["Literal"]["Value"]
        self.assertEqual(valor, "'O''Brien'")

    def test_projecoes_cobrem_a_hierarquia(self):
        from dadoscaged import extract
        _, cab = extract.montar_projecoes("CNAE 2.0 Classe", ["Saldo"])
        self.assertEqual(cab[:3], ["competencia", "ano", "mes"])
        self.assertIn("cod_classe", cab)
        self.assertIn("classe", cab)
        self.assertIn("divisao", cab)          # nível pai incluído
        self.assertNotIn("subclasse", cab)     # nível filho não incluído
        self.assertEqual(cab[-1], "saldo")

    def test_nivel_invalido(self):
        from dadoscaged import extract
        with self.assertRaises(ValueError):
            extract.montar_projecoes("CNAE 2.0 Inexistente", ["Saldo"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
