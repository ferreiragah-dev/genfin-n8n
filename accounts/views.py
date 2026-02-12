import calendar
from collections import defaultdict
from datetime import datetime, timedelta

import json
import os
import textwrap
from urllib import request as urllib_request
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db.models import Sum
from django.http import FileResponse, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    CreditCard,
    CreditCardExpense,
    FinancialEntry,
    PlannedExpense,
    PlannedIncome,
    PlannedReserve,
    TripPlan,
    TripToll,
    UserAccount,
    Vehicle,
    VehicleFrequentDestination,
    VehicleExpense,
)


def get_logged_user(request):
    phone = request.session.get("user_phone")
    if not phone:
        return None
    return UserAccount.objects.filter(phone_number=phone).first()


def _pdf_escape(text):
    return str(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_manual_pdf_bytes():
    version = os.getenv("GENFIN_MANUAL_VERSION", "v1.0")
    updated_at = timezone.now().strftime("%d/%m/%Y")
    generated_at = timezone.now().strftime("%d/%m/%Y %H:%M")

    pages = [
        {
            "cover": True,
            "title": "GenFin - Manual Oficial da Plataforma",
            "subtitle": "Guia de Uso, Operacao e Interpretacao Financeira",
            "items": [
                ("p", f"Versao do sistema: {version}"),
                ("p", f"Data de atualizacao: {updated_at}"),
                ("sp", ""),
                ("q", "Seu sistema pessoal de inteligencia financeira"),
            ],
        },
        {
            "title": "Como usar este manual",
            "items": [
                ("p", "Este manual atende tres perfis: iniciante, analitico e avancado."),
                ("li", "Iniciante: aprender telas e cadastros"),
                ("li", "Analitico: interpretar metricas e graficos"),
                ("li", "Avancado: planejar decisoes financeiras"),
                ("alert", "Recomendacao", "Na primeira utilizacao, leia os capitulos 1 a 3 antes de registrar movimentacoes."),
                ("h2", "Sumario"),
                ("li", "1) Mapa da Plataforma"),
                ("li", "2) Dashboard"),
                ("li", "3) Movimentacoes"),
                ("li", "4) Planejamento"),
                ("li", "5) Viagem"),
                ("li", "6) Cartoes"),
                ("li", "7) FAQ"),
                ("li", "8) Glossario"),
                ("li", "9) Roteiro tecnico e checklist"),
            ],
        },
        {
            "title": "1) Mapa da Plataforma",
            "items": [
                ("mono", "Dashboard"),
                ("mono", "  |- KPIs Financeiros"),
                ("mono", "  |- Inteligencia Financeira"),
                ("mono", "  |- Planejamento (donuts)"),
                ("mono", "  |- Graficos de categoria"),
                ("mono", "  `- Top 5 Gastos"),
                ("sp", ""),
                ("mono", "Movimentacoes"),
                ("mono", "  |- Entradas"),
                ("mono", "  |- Despesas"),
                ("mono", "  `- Comprovantes"),
                ("sp", ""),
                ("mono", "Planejamento"),
                ("mono", "  |- Despesas Fixas"),
                ("mono", "  |- Entradas Fixas"),
                ("mono", "  |- Reservas"),
                ("mono", "  `- Veiculos"),
                ("sp", ""),
                ("mono", "Viagem"),
                ("mono", "  |- Escolha de veiculo"),
                ("mono", "  |- Distancia (ida e volta)"),
                ("mono", "  |- Pedagios dinamicos"),
                ("mono", "  |- Hospedagem, refeicao e extras"),
                ("mono", "  `- Termometro de decisao financeira"),
                ("sp", ""),
                ("mono", "Cartoes"),
                ("mono", "  `- Faturas e limites"),
            ],
        },
        {
            "title": "2) Dashboard - Operacao e leitura",
            "items": [
                ("h2", "Objetivo"),
                ("p", "Visao executiva consolidada da saude financeira no periodo filtrado."),
                ("h2", "Indicadores e formulas"),
                ("li", "Receitas: soma das entradas do periodo"),
                ("li", "Despesas: soma das saidas do periodo"),
                ("li", "Saldo Atual: Receitas - Despesas"),
                ("li", "Taxa de Poupanca: (Saldo / Receitas) * 100"),
                ("li", "Burn Rate: Despesas / dias decorridos"),
                ("li", "Runway: saldo disponivel / burn diario"),
                ("li", "Tendencias: comparacao com periodo anterior equivalente"),
                ("concept", "Conceito: Burn Rate", "Mede velocidade de consumo do dinheiro. Quanto maior, maior a pressao no saldo."),
                ("tip", "Dica", "Sempre confirme o filtro de periodo antes de comparar percentuais."),
            ],
        },
        {
            "title": "2.1) Donuts e graficos do Dashboard",
            "items": [
                ("li", "Comprometimento Fixo: despesas fixas / entradas fixas"),
                ("li", "Cobertura de Fixas: quanto da fixa e coberta por renda fixa"),
                ("li", "Peso nas Saidas: participacao das fixas nas despesas"),
                ("li", "Reserva para Fixas: meses de cobertura da reserva"),
                ("li", "Contas Fixas Pagas: pago/total e pago/restante"),
                ("li", "Peso Veiculos: impacto do custo veicular no total"),
                ("li", "Resumo de Movimentacoes: hoje, 7 dias, 30 dias"),
                ("li", "Desempenho por Categoria: distribuicao dos gastos"),
                ("li", "Gastos por Dia da Semana: barras + calendario"),
                ("li", "Top 5 Maiores Gastos: ranking de maior impacto"),
                ("alert", "Atencao", "Nao interprete taxa de poupanca isoladamente sem analisar comprometimento fixo."),
            ],
        },
        {
            "title": "3) Movimentacoes",
            "items": [
                ("h2", "Objetivo"),
                ("p", "Controle detalhado de entradas e despesas com auditoria por comprovante."),
                ("h2", "O que fazer no modulo"),
                ("li", "Editar lancamentos"),
                ("li", "Excluir lancamentos"),
                ("li", "Anexar/remover comprovante por item"),
                ("li", "Filtrar por mes"),
                ("h2", "Como analisar"),
                ("li", "Volume alto + ticket baixo: dispersao operacional"),
                ("li", "Poucas categorias concentradas: risco de dependencia"),
                ("li", "Use comprovantes para conciliacao e rastreabilidade"),
            ],
        },
        {
            "title": "4) Planejamento (Fixas, Entradas, Reservas, Veiculos)",
            "items": [
                ("li", "Despesas Fixas: previsao e status pago/nao pago"),
                ("li", "Entradas Fixas: base recorrente de receita"),
                ("li", "Reservas: colchao para emergencia e metas"),
                ("li", "Veiculos: custo total de propriedade"),
                ("li", "Veiculos: cadastro de km/l e preco do combustivel por litro"),
                ("li", "Destinos frequentes: nome, periodicidade e distancia em km"),
                ("li", "Destinos com estacionamento pago: custo por ocorrencia"),
                ("li", "Custo Deslocamento: calculo mensal automatico"),
                ("h2", "Boas praticas"),
                ("li", "Cadastrar fixas no inicio do mes"),
                ("li", "Revisar pago/nao pago semanalmente"),
                ("li", "Separar custos essenciais de variaveis"),
                ("tip", "Dica", "Se os donuts de planejamento estiverem inconsistentes, revise dados recorrentes primeiro."),
            ],
        },
        {
            "title": "5) Viagem",
            "items": [
                ("h2", "Objetivo"),
                ("p", "Simular e decidir se e uma boa hora para viajar com base no painel financeiro."),
                ("h2", "Entradas da simulacao"),
                ("li", "Veiculo selecionado"),
                ("li", "Distancia de ida e distancia de volta"),
                ("li", "Pedagios dinamicos (quantos quiser, com preco por item)"),
                ("li", "Hospedagem, refeicao e gastos extras"),
                ("h2", "Calculos realizados"),
                ("li", "Combustivel da viagem = distancia_total / km_l * preco_litro"),
                ("li", "Total da viagem = combustivel + pedagios + hospedagem + refeicao + extras"),
                ("li", "% comprometimento do saldo"),
                ("li", "% comprometimento da receita mensal"),
                ("li", "Runway antes e depois da viagem"),
                ("h2", "Leitura visual"),
                ("li", "Termometro/velocimetro: Boa hora / Atencao / Evitar agora"),
                ("li", "Atualizacao em tempo real conforme preenchimento"),
                ("h2", "Operacao"),
                ("li", "Avaliacao instantanea sem salvar"),
                ("li", "Salvar viagem"),
                ("li", "Editar viagem salva"),
            ],
        },
        {
            "title": "6) Cartoes de Credito",
            "items": [
                ("li", "Cadastro: nome, final, limite, fechamento, vencimento, pontos/USD"),
                ("li", "Herdar cartao: consolidacao por limite/fatura"),
                ("h2", "Regra de competencia"),
                ("p", "Compra entra no mes da fatura que fecha, nao no mes da compra."),
                ("li", "Exemplo: fechamento 14 e vencimento 20"),
                ("li", "Compras de 15/01 a 14/02 pertencem a fatura de fevereiro"),
                ("h2", "Pontos estimados"),
                ("p", "Formula: (gasto BRL / cotacao USD-BRL) * pontos por dolar"),
                ("li", "Uso de limite > 70%: alerta de pressao financeira"),
            ],
        },
        {
            "title": "7) FAQ do produto",
            "items": [
                ("q", "Por que gastos de cartao aparecem em outro mes?"),
                ("p", "Porque o GenFin usa competencia da fatura."),
                ("q", "Por que a projecao de fim de mes muda ao longo do mes?"),
                ("p", "Porque burn rate e recalculado dinamicamente pelos dias decorridos."),
                ("q", "Como melhorar rapido os indicadores?"),
                ("p", "Atacar top 5 gastos, revisar fixas e reduzir uso de limite."),
                ("q", "Por que um percentual piorou sem mudar receita?"),
                ("p", "Possivel aumento de despesas ou alteracao de mix de gastos."),
                ("q", "Como o modulo Viagem decide se e boa hora para viajar?"),
                ("p", "Compara custo total da viagem com saldo, receita mensal e runway apos a viagem."),
                ("q", "Posso editar uma viagem apos salvar?"),
                ("p", "Sim. A viagem pode ser editada e o termometro recalcula automaticamente."),
            ],
        },
        {
            "title": "8) Glossario do GenFin",
            "items": [
                ("mono", "Burn Rate             Consumo medio diario"),
                ("mono", "Runway                Quanto tempo o saldo dura"),
                ("mono", "Comprometimento fixo  Percentual da renda em fixos"),
                ("mono", "Cobertura de fixas    Quanto da fixa e coberta por renda fixa"),
                ("mono", "IEF                   Indice de Eficiencia Financeira"),
                ("mono", "IRF                   Indice de Resiliencia Financeira"),
                ("mono", "Pressao financeira    Compromissos / receita"),
                ("mono", "Volatilidade          Variacao dos gastos no tempo"),
                ("mono", "Custo deslocamento    Custo mensal estimado por rotas frequentes"),
                ("mono", "Termometro de viagem  Indicador visual de viabilidade da viagem"),
            ],
        },
        {
            "title": "7.1) Inventario da Interface (Navegacao e Cabecalho)",
            "items": [
                ("h2", "Navegacao completa"),
                ("li", "Dashboard"),
                ("li", "Movimentacoes"),
                ("li", "Despesas Fixas"),
                ("li", "Entradas Fixas"),
                ("li", "Reservas"),
                ("li", "Veiculos"),
                ("li", "Viagem"),
                ("li", "Cartoes"),
                ("li", "Perfil"),
                ("h2", "Cabecalho e controles globais"),
                ("li", "GF / GenFin / Painel Financeiro"),
                ("li", "Tema: Dia / Noite"),
                ("li", "Switch de ambiente: Dev / Prod"),
                ("li", "Indicador de status"),
                ("li", "Visibilidade de valores"),
                ("li", "Exportacao em PDF"),
                ("li", "Notificacoes"),
                ("li", "Logout"),
                ("h2", "Filtros"),
                ("li", "Filtro por mes (JAN, FEV, ... DEZ)"),
                ("li", "Ano selecionado"),
                ("li", "Escala temporal: Semana / Mes / Ano"),
            ],
        },
        {
            "title": "7.2) Inventario da Interface (Cards e Inteligencia)",
            "items": [
                ("h2", "Cards de topo"),
                ("li", "Receitas (+)"),
                ("li", "Despesas (-)"),
                ("li", "Saldo Atual"),
                ("h2", "Inteligencia Financeira"),
                ("li", "Movimentacoes"),
                ("li", "Taxa de Poupanca"),
                ("li", "Burn Rate (R$/dia)"),
                ("li", "Projecao Fim do Mes"),
                ("li", "Custo Mensal Veiculo"),
                ("li", "Custo Deslocamento"),
                ("li", "Tendencia Saldo"),
                ("li", "Runway Pessoal"),
                ("li", "Tendencia Entradas"),
                ("li", "Tendencia Saidas"),
                ("h2", "Planejamento (donuts)"),
                ("li", "Comprometimento Fixo"),
                ("li", "Cobertura de Fixas"),
                ("li", "Peso nas Saidas"),
                ("li", "Reserva para Fixas"),
                ("li", "Contas Fixas Pagas"),
                ("li", "Peso Veiculos"),
            ],
        },
        {
            "title": "7.3) Inventario da Interface (Secoes Analiticas)",
            "items": [
                ("h2", "Eficiencia Financeira"),
                ("li", "Indice de Eficiencia (IEF)"),
                ("li", "Burn Rate Mensal"),
                ("li", "Runway Pessoal (meses)"),
                ("li", "Volatilidade de Gastos"),
                ("li", "Elasticidade por Renda"),
                ("li", "Previsibilidade"),
                ("li", "Radar de Saude Financeira"),
                ("li", "Volatilidade Mensal de Gastos"),
                ("li", "Gauge de Previsibilidade"),
                ("h2", "Seguranca Financeira"),
                ("li", "Indice de Resiliencia (IRF)"),
                ("li", "Cobertura de Emergencia"),
                ("li", "Exposicao a Liquidez"),
                ("li", "Custo Minimo de Sobrevivencia"),
                ("li", "Gauge de Resiliencia"),
                ("li", "Radar de Seguranca Financeira"),
                ("li", "Dependencia por Fonte de Renda"),
                ("li", "Fixos vs Variaveis"),
                ("li", "Gauge de Flexibilidade"),
                ("li", "Waterfall: Receita -> Essenciais -> Sobra"),
            ],
        },
        {
            "title": "7.4) Inventario da Interface (Risco, Resumos e Calendario)",
            "items": [
                ("h2", "Risco Financeiro Pessoal"),
                ("li", "Risco de Estouro Financeiro"),
                ("li", "Risco de Insolvencia (heur.)"),
                ("li", "Indice de Pressao Financeira"),
                ("li", "Prob. de Saldo Negativo"),
                ("li", "Stress Financeiro Mensal"),
                ("li", "Semaforo de Colapso"),
                ("li", "Gauge de Risco Financeiro"),
                ("li", "Linha de Stress Financeiro"),
                ("h2", "Resumo e distribuicoes"),
                ("li", "Resumo de Movimentacoes: Hoje / 7 dias / 30 dias"),
                ("li", "Desempenho por Categoria (% da Despesa)"),
                ("li", "Desempenho por Despesas Fixas (% do Planejado)"),
                ("li", "Gastos por Dia da Semana"),
                ("li", "Top 5 Maiores Gastos"),
                ("li", "Calendario de Gastos mensal"),
                ("li", "Mes e ano do calendario (ex.: Fevereiro/2026)"),
            ],
        },
        {
            "title": "7.5) Exemplo real de leitura (modelo completo)",
            "items": [
                ("p", "Exemplo de consolidacao de um mes (modelo de interpretacao):"),
                ("mono", "Receitas: R$ 15.015,85"),
                ("mono", "Despesas: R$ 486,45"),
                ("mono", "Saldo Atual: R$ 14.529,40"),
                ("mono", "Taxa de Poupanca: 97%"),
                ("mono", "Burn Rate diario: R$ 48,64"),
                ("mono", "Projecao fim do mes: R$ 13.653,79"),
                ("mono", "Runway: 902 dias"),
                ("mono", "Tendencia saldo: +R$ 14.424,67 vs mes passado"),
                ("mono", "Tendencia entradas: -R$ 984,15 vs mes passado"),
                ("mono", "Tendencia saidas: +R$ 15.408,82 vs mes passado"),
                ("mono", "Cartao: R$ 6.212,85 / R$ 6.260,00 (99% usado)"),
                ("mono", "Contas fixas pagas: 0/5"),
                ("mono", "Viagem simulada: ida/volta + pedagios + hospedagem + refeicao + extras"),
                ("mono", "Termometro de viagem: leitura visual de decisao"),
                ("h2", "Como analisar esse exemplo"),
                ("li", "Saldo alto no mes pode esconder risco de limite de cartao quase esgotado"),
                ("li", "Acompanhar 99% de uso do limite com prioridade"),
                ("li", "Contas fixas 0/5 pagas indica risco operacional de vencimentos"),
                ("li", "Validar calendario para concentracao de desembolso por dia"),
            ],
        },
        {
            "title": "9) Roteiro tecnico + Checklist final",
            "items": [
                ("h2", "Roteiro tecnico recomendado"),
                ("li", "Layout dark premium"),
                ("li", "Titulos hierarquicos"),
                ("li", "Caixas visuais: conceito, alerta, dica"),
                ("li", "Cabecalho com nome e versao"),
                ("li", "Rodape com pagina e data de geracao"),
                ("li", "FAQ e glossario obrigatorios"),
                ("h2", "Checklist de qualidade"),
                ("li", "Capa profissional"),
                ("li", "Sumario"),
                ("li", "Padrao por modulo"),
                ("li", "Exemplos praticos"),
                ("li", "Linguagem de produto"),
                ("q", f"Documento gerado em {generated_at}"),
            ],
        },
    ]

    objects = []

    def add_obj(content):
        objects.append(content)
        return len(objects)

    font_obj = add_obj("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_obj_ids = []
    content_obj_ids = []
    total_pages = len(pages)

    for idx, page in enumerate(pages, start=1):
        title = page.get("title", "")
        subtitle = page.get("subtitle", "")
        items = page.get("items", [])
        is_cover = bool(page.get("cover"))

        cmds = []
        cmds.append("0.04 0.07 0.12 rg 0 0 595 842 re f")
        if not is_cover:
            cmds.append("0.58 0.76 1 rg 40 816 515 1 re f")
            cmds.append("BT /F1 9 Tf 0.75 0.82 0.95 rg 42 824 Td (GenFin - Manual Oficial) Tj ET")
            cmds.append(f"BT /F1 9 Tf 0.75 0.82 0.95 rg 425 824 Td (Versao {_pdf_escape(version)}) Tj ET")

        cmds.append("BT")
        cmds.append("/F1 22 Tf")
        cmds.append("0.91 0.94 0.98 rg")
        cmds.append(f"1 0 0 1 50 782 Tm ({_pdf_escape(title)}) Tj")
        if subtitle:
            cmds.append("/F1 12 Tf")
            cmds.append("0.58 0.73 0.94 rg")
            cmds.append(f"1 0 0 1 50 758 Tm ({_pdf_escape(subtitle)}) Tj")
        cmds.append("ET")

        y = 728 if subtitle else 744
        for item in items:
            kind = item[0]
            if kind == "sp":
                y -= 8
                continue
            if kind == "h2":
                cmds.append("BT /F1 13 Tf 0.72 0.86 1 rg")
                cmds.append(f"1 0 0 1 50 {y} Tm ({_pdf_escape(item[1])}) Tj ET")
                y -= 18
                continue
            if kind in {"concept", "alert", "tip"}:
                stroke = {"concept": "0.25 0.68 1", "alert": "0.95 0.35 0.35", "tip": "0.30 0.82 0.52"}[kind]
                title_box = item[1]
                body_box = item[2]
                cmds.append(f"{stroke} RG 50 {y-40} 495 46 re S")
                cmds.append("BT /F1 10 Tf 0.90 0.93 0.98 rg")
                cmds.append(f"1 0 0 1 58 {y-16} Tm ({_pdf_escape(title_box)}) Tj")
                yy = y - 30
                for part in textwrap.wrap(body_box, width=90)[:2]:
                    cmds.append(f"1 0 0 1 58 {yy} Tm ({_pdf_escape(part)}) Tj")
                    yy -= 12
                cmds.append("ET")
                y -= 54
                continue

            text = item[1]
            if kind == "li":
                text = f"- {text}"
            if kind == "q":
                text = f'"{text}"'
            wrap_width = 92 if kind == "mono" else 96
            color = "0.82 0.88 0.95" if kind == "mono" else "0.90 0.93 0.98"
            size = 10 if kind == "mono" else 11
            for part in textwrap.wrap(text, width=wrap_width):
                cmds.append(f"BT /F1 {size} Tf {color} rg 1 0 0 1 50 {y} Tm ({_pdf_escape(part)}) Tj ET")
                y -= 14

        cmds.append("0.58 0.76 1 rg 40 28 515 1 re f")
        footer = f"Pagina {idx}/{total_pages} | Gerado em {generated_at}"
        cmds.append(f"BT /F1 9 Tf 0.75 0.82 0.95 rg 50 14 Td ({_pdf_escape(footer)}) Tj ET")

        stream = "\n".join(cmds)
        stream_len = len(stream.encode("latin-1", errors="ignore"))
        content_obj_id = add_obj(f"<< /Length {stream_len} >>\nstream\n{stream}\nendstream")
        content_obj_ids.append(content_obj_id)
        page_obj_ids.append(add_obj("__PAGE__"))

    kids = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
    pages_obj = add_obj(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_obj_ids)} >>")
    for i, page_obj_id in enumerate(page_obj_ids):
        content_id = content_obj_ids[i]
        objects[page_obj_id - 1] = (
            f"<< /Type /Page /Parent {pages_obj} 0 R /MediaBox [0 0 595 842] "
            f"/Resources << /Font << /F1 {font_obj} 0 R >> >> /Contents {content_id} 0 R >>"
        )

    catalog_obj = add_obj(f"<< /Type /Catalog /Pages {pages_obj} 0 R >>")
    result = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(result))
        result.extend(f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1", errors="ignore"))
    xref_pos = len(result)
    result.extend(f"xref\n0 {len(objects)+1}\n".encode("latin-1"))
    result.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        result.extend(f"{off:010d} 00000 n \n".encode("latin-1"))
    trailer = f"trailer\n<< /Size {len(objects)+1} /Root {catalog_obj} 0 R >>\nstartxref\n{xref_pos}\n%%EOF"
    result.extend(trailer.encode("latin-1"))
    return bytes(result)


def parse_bool(value):
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def resolve_billing_owner(card, cards_by_id=None):
    current = card
    visited = set()
    while current and current.parent_card_id and current.id not in visited:
        visited.add(current.id)
        if cards_by_id is not None:
            current = cards_by_id.get(current.parent_card_id)
        else:
            current = current.parent_card
    return current


def get_owner_id_for_card(card, cards_by_id):
    owner = resolve_billing_owner(card, cards_by_id)
    return owner.id if owner else card.id


def clamp_day(year, month, day):
    max_day = calendar.monthrange(year, month)[1]
    return max(1, min(int(day), max_day))


def shift_month(year, month, delta):
    idx = (year * 12 + (month - 1)) + delta
    new_year = idx // 12
    new_month = (idx % 12) + 1
    return new_year, new_month


def fetch_usd_brl_quote():
    url = "https://economia.awesomeapi.com.br/json/last/USD-BRL"
    fallback_rate = float(os.getenv("GENFIN_USD_BRL_FALLBACK", "5.2"))
    try:
        req = urllib_request.Request(
            url,
            headers={
                "User-Agent": "GenFin/1.0 (+https://genfin.local)",
                "Accept": "application/json",
            },
        )
        with urllib_request.urlopen(req, timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        quote = payload.get("USDBRL", {}) if isinstance(payload, dict) else {}
        bid = quote.get("bid")
        ask = quote.get("ask")
        raw_rate = bid if bid is not None else ask
        rate = float(raw_rate) if raw_rate is not None else 0.0
        if rate <= 0:
            raise ValueError("USD/BRL invalido")
        return {
            "rate": rate,
            "timestamp": quote.get("timestamp"),
            "create_date": quote.get("create_date"),
            "name": quote.get("name"),
            "source": "awesomeapi",
        }
    except Exception:
        return {
            "rate": fallback_rate if fallback_rate > 0 else 5.2,
            "timestamp": None,
            "create_date": None,
            "name": "Cotacao fallback",
            "source": "fallback",
        }


def card_invoice_period_and_due(card, purchase_date):
    # Regra de competência:
    # 1) compra até o fechamento entra na fatura que fecha no mesmo mês
    # 2) compra após fechamento entra na fatura que fecha no mês seguinte
    # 3) competência financeira = mês da fatura que FECHA (não mês seguinte)
    # Ex.: fechamento 14 / vencimento 20
    # compras de 15/01 até 14/02 => fatura de fevereiro (competência fevereiro)
    close_year = purchase_date.year
    close_month = purchase_date.month
    closing_day = int(getattr(card, "closing_day", 20) or 20)
    if purchase_date.day > closing_day:
        close_year, close_month = shift_month(close_year, close_month, 1)

    due_year, due_month = close_year, close_month
    # Se o dia de vencimento vier antes/igual ao fechamento, desloca para o mês seguinte.
    if int(card.due_day) <= closing_day:
        due_year, due_month = shift_month(close_year, close_month, 1)
    due_day = clamp_day(due_year, due_month, int(card.due_day))
    due_date = datetime(due_year, due_month, due_day).date()
    return close_year, close_month, due_date, close_year, close_month


def sync_credit_card_bills(user, card):
    cards = list(user.credit_cards.select_related("parent_card").all())
    cards_by_id = {c.id: c for c in cards}
    owner = resolve_billing_owner(cards_by_id.get(card.id, card), cards_by_id) or card
    owner_id = owner.id
    owner_card = cards_by_id.get(owner_id, owner)

    family_card_ids = [
        c.id
        for c in cards
        if get_owner_id_for_card(c, cards_by_id) == owner_id
    ]

    grouped = defaultdict(lambda: {"amount": 0.0, "due_date": None, "close_year": None, "close_month": None})
    expenses = user.credit_card_expenses.filter(card_id__in=family_card_ids).order_by("date", "id")
    for expense in expenses:
        close_year, close_month, due_date, comp_year, comp_month = card_invoice_period_and_due(owner_card, expense.date)
        key = f"CC:{owner_id}:{comp_year:04d}-{comp_month:02d}"
        grouped[key]["amount"] += float(expense.amount or 0)
        grouped[key]["due_date"] = due_date
        grouped[key]["close_year"] = close_year
        grouped[key]["close_month"] = close_month

    active_keys = set(grouped.keys())
    existing_qs = user.planned_expenses.filter(source_key__startswith=f"CC:{owner_id}:")
    for planned in existing_qs:
        if planned.source_key not in active_keys:
            planned.delete()

    for source_key, data in grouped.items():
        due_date = data["due_date"]
        total = round(data["amount"], 2)
        period = source_key.split(":")[-1]
        close_year = data["close_year"]
        close_month = data["close_month"]
        defaults = {
            "date": due_date,
            "category": f"Fatura Cartão {owner_card.last4}",
            "description": f"Fatura cartão final {owner_card.last4} (fechamento {close_month:02d}/{close_year}, competência {period})",
            "amount": total,
            "is_recurring": True,
        }
        planned, created = PlannedExpense.objects.get_or_create(
            user=user,
            source_key=source_key,
            defaults=defaults,
        )
        if not created:
            planned.date = defaults["date"]
            planned.category = defaults["category"]
            planned.description = defaults["description"]
            planned.amount = defaults["amount"]
            planned.is_recurring = True
            planned.save()


class ValidatePhoneView(APIView):
    def post(self, request):
        phone_number = request.data.get("phone_number")

        if not phone_number:
            return Response(
                {"error": "phone_number is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        exists = UserAccount.objects.filter(
            phone_number=phone_number,
            is_active=True,
        ).exists()

        if exists:
            return Response(
                {"message": "User exists"},
                status=status.HTTP_200_OK,
            )

        return Response(
            {"message": "User not found"},
            status=status.HTTP_400_BAD_REQUEST,
        )


@method_decorator(csrf_exempt, name="dispatch")
class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        first_name = str(request.data.get("first_name", "")).strip()
        last_name = str(request.data.get("last_name", "")).strip()
        email = str(request.data.get("email", "")).strip().lower()
        phone_number = str(request.data.get("phone_number", "")).strip()
        password = str(request.data.get("password", ""))

        if not first_name or not last_name or not email or not phone_number or not password:
            return Response(
                {"error": "first_name, last_name, email, phone_number e password sao obrigatorios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if len(password) < 6:
            return Response(
                {"error": "Senha deve ter pelo menos 6 caracteres"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            validate_email(email)
        except ValidationError:
            return Response(
                {"error": "Email invalido"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if UserAccount.objects.filter(phone_number=phone_number).exists():
            return Response(
                {"error": "Telefone ja cadastrado"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if UserAccount.objects.filter(email=email).exists():
            return Response(
                {"error": "Email ja cadastrado"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = UserAccount(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
            is_active=True,
        )
        user.set_password(password)
        user.save()

        request.session["user_phone"] = user.phone_number

        return Response(
            {"message": "Cadastro realizado com sucesso"},
            status=status.HTTP_201_CREATED,
        )


class FinancialEntryCreateView(APIView):
    def post(self, request):
        phone_number = request.data.get("phone_number")
        categoria = request.data.get("categoria")
        data_str = request.data.get("data")

        receita = request.data.get("receita")
        despesa = request.data.get("despesa")

        if not phone_number or not categoria or not data_str:
            return Response(
                {"error": "phone_number, categoria e data sao obrigatorios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if receita is None and despesa is None:
            return Response(
                {"error": "Informe receita ou despesa"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            entry_date = datetime.strptime(data_str, "%d/%m/%Y").date()
        except ValueError:
            return Response(
                {"error": "Formato de data invalido. Use DD/MM/YYYY"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = UserAccount.objects.get(phone_number=phone_number)
        except UserAccount.DoesNotExist:
            return Response(
                {"error": "Usuario nao encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if receita is not None:
            entry_type = "RECEITA"
            amount = receita
        else:
            entry_type = "DESPESA"
            amount = despesa

        entry = FinancialEntry.objects.create(
            user=user,
            entry_type=entry_type,
            amount=amount,
            category=categoria,
            date=entry_date,
        )

        return Response(
            {
                "message": "Lancamento criado com sucesso",
                "id": entry.id,
                "tipo": entry.entry_type,
                "valor": entry.amount,
                "categoria": entry.category,
                "data": entry.date,
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name="dispatch")
class PhoneLoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        phone_number = request.data.get("phone_number")
        password = request.data.get("password")

        if not phone_number or not password:
            return Response(
                {"error": "phone_number e password sao obrigatorios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            user = UserAccount.objects.get(
                phone_number=phone_number,
                is_active=True,
            )
        except UserAccount.DoesNotExist:
            return Response(
                {"error": "Usuario nao encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not user.check_password(password):
            return Response(
                {"error": "Senha invalida"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        request.session["user_phone"] = user.phone_number

        return Response(
            {"message": "Login realizado com sucesso"},
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class ProfileView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        return Response(
            {
                "first_name": user.first_name or "",
                "last_name": user.last_name or "",
                "email": user.email or "",
                "phone_number": user.phone_number or "",
                "address_line": user.address_line or "",
                "city": user.city or "",
                "state": user.state or "",
                "zip_code": user.zip_code or "",
                "country": user.country or "",
            }
        )

    def put(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        first_name = str(request.data.get("first_name", user.first_name)).strip()
        last_name = str(request.data.get("last_name", user.last_name)).strip()
        email = str(request.data.get("email", user.email or "")).strip().lower()
        phone_number = str(request.data.get("phone_number", user.phone_number)).strip()
        address_line = str(request.data.get("address_line", user.address_line or "")).strip()
        city = str(request.data.get("city", user.city or "")).strip()
        state_val = str(request.data.get("state", user.state or "")).strip()
        zip_code = str(request.data.get("zip_code", user.zip_code or "")).strip()
        country = str(request.data.get("country", user.country or "")).strip()
        password = str(request.data.get("password", "")).strip()

        if not phone_number:
            return Response({"error": "Numero de telefone e obrigatorio"}, status=status.HTTP_400_BAD_REQUEST)
        if UserAccount.objects.exclude(id=user.id).filter(phone_number=phone_number).exists():
            return Response({"error": "Telefone ja cadastrado"}, status=status.HTTP_400_BAD_REQUEST)

        if email:
            try:
                validate_email(email)
            except ValidationError:
                return Response({"error": "Email invalido"}, status=status.HTTP_400_BAD_REQUEST)
            if UserAccount.objects.exclude(id=user.id).filter(email=email).exists():
                return Response({"error": "Email ja cadastrado"}, status=status.HTTP_400_BAD_REQUEST)

        if password and len(password) < 6:
            return Response({"error": "Senha deve ter pelo menos 6 caracteres"}, status=status.HTTP_400_BAD_REQUEST)

        user.first_name = first_name
        user.last_name = last_name
        user.email = email or None
        user.phone_number = phone_number
        user.address_line = address_line
        user.city = city
        user.state = state_val
        user.zip_code = zip_code
        user.country = country
        if password:
            user.set_password(password)
        user.save()
        request.session["user_phone"] = user.phone_number
        return Response({"message": "Perfil atualizado com sucesso"})


class UserManualPdfView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        pdf_bytes = build_manual_pdf_bytes()
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = 'attachment; filename="Manual-GenFin.pdf"'
        return response


class DashboardView(APIView):
    def get(self, request):
        user = get_logged_user(request)

        if not user:
            return Response(
                {"error": "Nao autenticado"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        receitas = user.entries.filter(entry_type="RECEITA")
        despesas = user.entries.filter(entry_type="DESPESA")

        total_receita = receitas.aggregate(total=Sum("amount"))["total"] or 0
        total_despesa = despesas.aggregate(total=Sum("amount"))["total"] or 0

        return Response(
            {
                "phone_number": user.phone_number,
                "total_receita": total_receita,
                "total_despesa": total_despesa,
                "saldo": total_receita - total_despesa,
            },
            status=status.HTTP_200_OK,
        )


@ensure_csrf_cookie
def landing_page(request):
    if request.session.get("user_phone"):
        return redirect("/dashboard/")
    return render(request, "landing.html")


@ensure_csrf_cookie
def login_page(request):
    return render(request, "login.html")


@ensure_csrf_cookie
def dashboard_page(request):
    if not request.session.get("user_phone"):
        return redirect("/login/")
    return render(request, "dashboard.html")


@ensure_csrf_cookie
def transactions_page(request):
    if not request.session.get("user_phone"):
        return redirect("/login/")
    return render(request, "transactions.html")


@ensure_csrf_cookie
def fixed_expenses_page(request):
    if not request.session.get("user_phone"):
        return redirect("/login/")
    return render(request, "fixed_expenses.html")


@ensure_csrf_cookie
def fixed_incomes_page(request):
    if not request.session.get("user_phone"):
        return redirect("/login/")
    return render(request, "fixed_incomes.html")


@ensure_csrf_cookie
def reserves_page(request):
    if not request.session.get("user_phone"):
        return redirect("/login/")
    return render(request, "reserves.html")


@ensure_csrf_cookie
def vehicles_page(request):
    if not request.session.get("user_phone"):
        return redirect("/login/")
    return render(request, "vehicles.html")


@ensure_csrf_cookie
def credit_cards_page(request):
    if not request.session.get("user_phone"):
        return redirect("/login/")
    return render(request, "credit_cards.html")


@ensure_csrf_cookie
def profile_page(request):
    if not request.session.get("user_phone"):
        return redirect("/login/")
    return render(request, "profile.html")


@ensure_csrf_cookie
def trips_page(request):
    if not request.session.get("user_phone"):
        return redirect("/login/")
    return render(request, "trips.html")


@ensure_csrf_cookie
def logout_page(request):
    request.session.flush()
    return redirect("/login/")


class FinancialEntryListView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            limit = int(request.query_params.get("limit", 20))
        except ValueError:
            limit = 20
        limit = max(1, min(limit, 500))

        entries = user.entries.order_by("-date")[:limit]

        return Response(
            [
                {
                    "id": e.id,
                    "date": e.date.strftime("%d/%m/%Y"),
                    "category": e.category,
                    "entry_type": e.entry_type,
                    "amount": e.amount,
                    "has_receipt": bool(e.receipt_file),
                    "receipt_url": f"/api/entries/{e.id}/receipt/" if e.receipt_file else None,
                }
                for e in entries
            ]
        )


@method_decorator(csrf_exempt, name="dispatch")
class FinancialEntryDetailView(APIView):
    def put(self, request, entry_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            entry = user.entries.get(id=entry_id)
        except FinancialEntry.DoesNotExist:
            return Response(
                {"error": "Movimentacao nao encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        category = request.data.get("category")
        amount = request.data.get("amount")
        data_str = request.data.get("date")

        if not category or amount in (None, "") or not data_str:
            return Response(
                {"error": "date, category e amount sao obrigatorios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        entry_type = request.data.get("entry_type")
        if entry_type and entry_type in {"RECEITA", "DESPESA"}:
            entry.entry_type = entry_type

        try:
            if "/" in str(data_str):
                entry.date = datetime.strptime(data_str, "%d/%m/%Y").date()
            else:
                entry.date = datetime.strptime(data_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"error": "Formato de data invalido. Use DD/MM/YYYY ou YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        entry.category = category
        entry.amount = amount
        entry.save()

        return Response({"message": "Movimentacao atualizada"}, status=status.HTTP_200_OK)

    def delete(self, request, entry_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            entry = user.entries.get(id=entry_id)
        except FinancialEntry.DoesNotExist:
            return Response(
                {"error": "Movimentacao nao encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        entry.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_exempt, name="dispatch")
class FinancialEntryReceiptView(APIView):
    def get(self, request, entry_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            entry = user.entries.get(id=entry_id)
        except FinancialEntry.DoesNotExist:
            return Response(
                {"error": "Movimentacao nao encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not entry.receipt_file:
            return Response(
                {"error": "Comprovante nao encontrado"},
                status=status.HTTP_404_NOT_FOUND,
            )
        filename = entry.receipt_file.name.rsplit("/", 1)[-1]
        return FileResponse(entry.receipt_file.open("rb"), as_attachment=False, filename=filename)

    def post(self, request, entry_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            entry = user.entries.get(id=entry_id)
        except FinancialEntry.DoesNotExist:
            return Response(
                {"error": "Movimentacao nao encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        receipt = request.FILES.get("receipt")
        if not receipt:
            return Response(
                {"error": "Arquivo obrigatorio no campo receipt"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        max_bytes = 10 * 1024 * 1024
        if getattr(receipt, "size", 0) > max_bytes:
            return Response(
                {"error": "Arquivo muito grande (max 10MB)"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        entry.receipt_file = receipt
        entry.save(update_fields=["receipt_file"])
        return Response(
            {
                "message": "Comprovante anexado",
                "has_receipt": True,
                "receipt_url": f"/api/entries/{entry.id}/receipt/",
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, entry_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            entry = user.entries.get(id=entry_id)
        except FinancialEntry.DoesNotExist:
            return Response(
                {"error": "Movimentacao nao encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )
        if entry.receipt_file:
            entry.receipt_file.delete(save=False)
            entry.receipt_file = None
            entry.save(update_fields=["receipt_file"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class DashboardCategoryView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        data = (
            user.entries.filter(entry_type="DESPESA")
            .values("category")
            .annotate(total=Sum("amount"))
            .order_by("-total")
        )

        return Response(list(data))


class PlannerListView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        data = user.planned_expenses.all().order_by("date")

        return Response(
            [
                {
                    "id": p.id,
                    "date": p.date.strftime("%Y-%m-%d"),
                    "category": p.category,
                    "description": p.description,
                    "amount": p.amount,
                    "is_recurring": p.is_recurring,
                    "is_paid": p.is_paid,
                }
                for p in data
            ]
        )


class PlannedIncomeListView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        data = user.planned_incomes.all().order_by("date")

        return Response(
            [
                {
                    "id": p.id,
                    "date": p.date.strftime("%Y-%m-%d"),
                    "category": p.category,
                    "description": p.description,
                    "amount": p.amount,
                    "is_recurring": p.is_recurring,
                }
                for p in data
            ]
        )


class PlannedReserveListView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        data = user.planned_reserves.all().order_by("date")

        return Response(
            [
                {
                    "id": p.id,
                    "date": p.date.strftime("%Y-%m-%d"),
                    "category": p.category,
                    "description": p.description,
                    "amount": p.amount,
                    "is_recurring": p.is_recurring,
                }
                for p in data
            ]
        )


class VehicleListView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        data = user.vehicles.all().order_by("-created_at")
        return Response(
            [
                {
                    "id": v.id,
                    "name": v.name,
                    "brand": v.brand,
                    "model": v.model,
                    "year": v.year,
                    "fipe_value": v.fipe_value,
                    "fipe_variation_percent": v.fipe_variation_percent,
                    "documentation_cost": v.documentation_cost,
                    "ipva_cost": v.ipva_cost,
                    "licensing_cost": v.licensing_cost,
                    "financing_remaining_installments": v.financing_remaining_installments,
                    "financing_installment_value": v.financing_installment_value,
                    "fuel_km_per_liter": v.fuel_km_per_liter,
                    "fuel_price_per_liter": v.fuel_price_per_liter,
                }
                for v in data
            ]
        )


@method_decorator(csrf_exempt, name="dispatch")
class VehicleCreateView(APIView):
    def post(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        name = str(request.data.get("name", "")).strip()
        if not name:
            return Response({"error": "name e obrigatorio"}, status=status.HTTP_400_BAD_REQUEST)

        vehicle = Vehicle.objects.create(
            user=user,
            name=name,
            brand=request.data.get("brand", "") or "",
            model=request.data.get("model", "") or "",
            year=request.data.get("year") or None,
            fipe_value=request.data.get("fipe_value") or 0,
            fipe_variation_percent=request.data.get("fipe_variation_percent") or 0,
            documentation_cost=request.data.get("documentation_cost") or 0,
            ipva_cost=request.data.get("ipva_cost") or 0,
            licensing_cost=request.data.get("licensing_cost") or 0,
            financing_remaining_installments=request.data.get("financing_remaining_installments") or 0,
            financing_installment_value=request.data.get("financing_installment_value") or 0,
            fuel_km_per_liter=request.data.get("fuel_km_per_liter") or 0,
            fuel_price_per_liter=request.data.get("fuel_price_per_liter") or 0,
        )
        return Response({"message": "Veiculo criado", "id": vehicle.id}, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class VehicleDetailView(APIView):
    def put(self, request, vehicle_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            vehicle = user.vehicles.get(id=vehicle_id)
        except Vehicle.DoesNotExist:
            return Response({"error": "Veiculo nao encontrado"}, status=status.HTTP_404_NOT_FOUND)

        name = str(request.data.get("name", "")).strip()
        if not name:
            return Response({"error": "name e obrigatorio"}, status=status.HTTP_400_BAD_REQUEST)

        vehicle.name = name
        vehicle.brand = request.data.get("brand", "") or ""
        vehicle.model = request.data.get("model", "") or ""
        vehicle.year = request.data.get("year") or None
        vehicle.fipe_value = request.data.get("fipe_value") or 0
        vehicle.fipe_variation_percent = request.data.get("fipe_variation_percent") or 0
        vehicle.documentation_cost = request.data.get("documentation_cost") or 0
        vehicle.ipva_cost = request.data.get("ipva_cost") or 0
        vehicle.licensing_cost = request.data.get("licensing_cost") or 0
        vehicle.financing_remaining_installments = request.data.get("financing_remaining_installments") or 0
        vehicle.financing_installment_value = request.data.get("financing_installment_value") or 0
        vehicle.fuel_km_per_liter = request.data.get("fuel_km_per_liter") or 0
        vehicle.fuel_price_per_liter = request.data.get("fuel_price_per_liter") or 0
        vehicle.save()
        return Response({"message": "Veiculo atualizado"}, status=status.HTTP_200_OK)

    def delete(self, request, vehicle_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            vehicle = user.vehicles.get(id=vehicle_id)
        except Vehicle.DoesNotExist:
            return Response({"error": "Veiculo nao encontrado"}, status=status.HTTP_404_NOT_FOUND)
        vehicle.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class VehicleExpenseListView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        data = user.vehicle_expenses.select_related("vehicle").all().order_by("-date")
        vehicle_id = request.query_params.get("vehicle_id")
        if vehicle_id:
            data = data.filter(vehicle_id=vehicle_id)

        return Response(
            [
                {
                    "id": e.id,
                    "vehicle_id": e.vehicle_id,
                    "vehicle_name": e.vehicle.name,
                    "date": e.date.strftime("%Y-%m-%d"),
                    "expense_type": e.expense_type,
                    "description": e.description,
                    "amount": e.amount,
                    "is_recurring": e.is_recurring,
                }
                for e in data
            ]
        )


@method_decorator(csrf_exempt, name="dispatch")
class VehicleExpenseCreateView(APIView):
    def post(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        vehicle_id = request.data.get("vehicle_id")
        date = request.data.get("date")
        expense_type = request.data.get("expense_type")
        amount = request.data.get("amount")
        if not vehicle_id or not date or not expense_type or amount in (None, ""):
            return Response({"error": "vehicle_id, date, expense_type e amount sao obrigatorios"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            vehicle = user.vehicles.get(id=vehicle_id)
        except Vehicle.DoesNotExist:
            return Response({"error": "Veiculo nao encontrado"}, status=status.HTTP_404_NOT_FOUND)

        item = VehicleExpense.objects.create(
            user=user,
            vehicle=vehicle,
            date=date,
            expense_type=expense_type,
            description=request.data.get("description", "") or "",
            amount=amount,
            is_recurring=parse_bool(request.data.get("is_recurring", False)),
        )
        return Response({"message": "Gasto criado", "id": item.id}, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class VehicleExpenseDetailView(APIView):
    def put(self, request, expense_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            item = user.vehicle_expenses.get(id=expense_id)
        except VehicleExpense.DoesNotExist:
            return Response({"error": "Gasto nao encontrado"}, status=status.HTTP_404_NOT_FOUND)

        vehicle_id = request.data.get("vehicle_id")
        if vehicle_id:
            try:
                item.vehicle = user.vehicles.get(id=vehicle_id)
            except Vehicle.DoesNotExist:
                return Response({"error": "Veiculo nao encontrado"}, status=status.HTTP_404_NOT_FOUND)

        date = request.data.get("date")
        expense_type = request.data.get("expense_type")
        amount = request.data.get("amount")
        if not date or not expense_type or amount in (None, ""):
            return Response({"error": "date, expense_type e amount sao obrigatorios"}, status=status.HTTP_400_BAD_REQUEST)

        item.date = date
        item.expense_type = expense_type
        item.description = request.data.get("description", "") or ""
        item.amount = amount
        item.is_recurring = parse_bool(request.data.get("is_recurring", False))
        item.save()
        return Response({"message": "Gasto atualizado"}, status=status.HTTP_200_OK)

    def delete(self, request, expense_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            item = user.vehicle_expenses.get(id=expense_id)
        except VehicleExpense.DoesNotExist:
            return Response({"error": "Gasto nao encontrado"}, status=status.HTTP_404_NOT_FOUND)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


def destination_occurrences_per_month(periodicity):
    periodicity_map = {
        "DIARIO": 30.0,
        "SEMANAL": 4.33,
        "QUINZENAL": 2.0,
        "MENSAL": 1.0,
    }
    return periodicity_map.get(str(periodicity or "").upper(), 1.0)


def evaluate_trip_payload(user, payload):
    today = timezone.now().date()
    month = today.month
    year = today.year
    month_entries = user.entries.filter(date__year=year, date__month=month)
    total_receita_mes = float(month_entries.filter(entry_type="RECEITA").aggregate(total=Sum("amount"))["total"] or 0)
    total_despesa_mes = float(month_entries.filter(entry_type="DESPESA").aggregate(total=Sum("amount"))["total"] or 0)
    total_receita_all = float(user.entries.filter(entry_type="RECEITA").aggregate(total=Sum("amount"))["total"] or 0)
    total_despesa_all = float(user.entries.filter(entry_type="DESPESA").aggregate(total=Sum("amount"))["total"] or 0)
    saldo_atual = total_receita_all - total_despesa_all
    recurring_fixed = float(user.planned_expenses.filter(is_recurring=True).aggregate(total=Sum("amount"))["total"] or 0)

    vehicle_id = payload.get("vehicle_id")
    vehicle = user.vehicles.filter(id=vehicle_id).first()
    if not vehicle:
        return {"error": "Veiculo nao encontrado"}

    distance_km = float(payload.get("distance_km") or 0)
    lodging_cost = float(payload.get("lodging_cost") or 0)
    meal_cost = float(payload.get("meal_cost") or 0)
    extra_cost = float(payload.get("extra_cost") or 0)
    tolls = payload.get("tolls") or []
    toll_total = 0.0
    for item in tolls:
        toll_total += float((item or {}).get("amount") or 0)

    km_per_liter = float(vehicle.fuel_km_per_liter or 0)
    fuel_price = float(vehicle.fuel_price_per_liter or 0)
    fuel_cost = (distance_km / km_per_liter) * fuel_price if km_per_liter > 0 else 0.0

    total_trip_cost = fuel_cost + toll_total + lodging_cost + meal_cost + extra_cost
    burn_daily = total_despesa_mes / max(today.day, 1)
    runway_before = saldo_atual / burn_daily if burn_daily > 0 else 0
    runway_after = (saldo_atual - total_trip_cost) / burn_daily if burn_daily > 0 else 0
    commitment_pct_balance = (total_trip_cost / saldo_atual * 100) if saldo_atual > 0 else 999
    commitment_pct_income = (total_trip_cost / total_receita_mes * 100) if total_receita_mes > 0 else 999

    if saldo_atual <= 0:
        recommendation = "Nao recomendado"
        level = "alto"
        reason = "Saldo atual negativo."
    elif commitment_pct_balance > 40 or runway_after < 30:
        recommendation = "Alto impacto"
        level = "alto"
        reason = "Viagem compromete parcela elevada do caixa."
    elif commitment_pct_balance > 20 or commitment_pct_income > 30:
        recommendation = "Atenção"
        level = "medio"
        reason = "Viagem exige planejamento para nao apertar o mes."
    else:
        recommendation = "Boa hora para viajar"
        level = "baixo"
        reason = "Comprometimento dentro de faixa saudavel."

    return {
        "vehicle_name": vehicle.name,
        "distance_km": round(distance_km, 2),
        "fuel_cost": round(fuel_cost, 2),
        "toll_total": round(toll_total, 2),
        "lodging_cost": round(lodging_cost, 2),
        "meal_cost": round(meal_cost, 2),
        "extra_cost": round(extra_cost, 2),
        "trip_total_cost": round(total_trip_cost, 2),
        "monthly_income": round(total_receita_mes, 2),
        "monthly_expense": round(total_despesa_mes, 2),
        "current_balance": round(saldo_atual, 2),
        "recurring_fixed": round(recurring_fixed, 2),
        "burn_daily": round(burn_daily, 2),
        "runway_days_before": round(runway_before, 1),
        "runway_days_after": round(runway_after, 1),
        "commitment_pct_balance": round(commitment_pct_balance, 2),
        "commitment_pct_income": round(commitment_pct_income, 2),
        "recommendation": recommendation,
        "risk_level": level,
        "reason": reason,
    }


class VehicleDestinationListView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        data = user.vehicle_destinations.select_related("vehicle").all().order_by("-created_at")
        vehicle_id = request.query_params.get("vehicle_id")
        if vehicle_id:
            data = data.filter(vehicle_id=vehicle_id)

        return Response(
            [
                {
                    "id": d.id,
                    "vehicle_id": d.vehicle_id,
                    "vehicle_name": d.vehicle.name,
                    "name": d.name,
                    "periodicity": d.periodicity,
                    "distance_km": d.distance_km,
                    "has_paid_parking": d.has_paid_parking,
                    "parking_cost": d.parking_cost,
                }
                for d in data
            ]
        )


@method_decorator(csrf_exempt, name="dispatch")
class VehicleDestinationCreateView(APIView):
    def post(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        vehicle_id = request.data.get("vehicle_id")
        name = str(request.data.get("name", "")).strip()
        periodicity = str(request.data.get("periodicity", "SEMANAL")).upper()
        distance_km = request.data.get("distance_km")
        if not vehicle_id or not name or distance_km in (None, ""):
            return Response({"error": "vehicle_id, name e distance_km sao obrigatorios"}, status=status.HTTP_400_BAD_REQUEST)
        if periodicity not in {"DIARIO", "SEMANAL", "QUINZENAL", "MENSAL"}:
            return Response({"error": "periodicity invalida"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            vehicle = user.vehicles.get(id=vehicle_id)
        except Vehicle.DoesNotExist:
            return Response({"error": "Veiculo nao encontrado"}, status=status.HTTP_404_NOT_FOUND)

        item = VehicleFrequentDestination.objects.create(
            user=user,
            vehicle=vehicle,
            name=name,
            periodicity=periodicity,
            distance_km=distance_km,
            has_paid_parking=parse_bool(request.data.get("has_paid_parking", False)),
            parking_cost=request.data.get("parking_cost") or 0,
        )
        return Response({"message": "Destino frequente criado", "id": item.id}, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class VehicleDestinationDetailView(APIView):
    def put(self, request, destination_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            item = user.vehicle_destinations.get(id=destination_id)
        except VehicleFrequentDestination.DoesNotExist:
            return Response({"error": "Destino nao encontrado"}, status=status.HTTP_404_NOT_FOUND)

        vehicle_id = request.data.get("vehicle_id")
        if vehicle_id:
            try:
                item.vehicle = user.vehicles.get(id=vehicle_id)
            except Vehicle.DoesNotExist:
                return Response({"error": "Veiculo nao encontrado"}, status=status.HTTP_404_NOT_FOUND)

        name = str(request.data.get("name", item.name)).strip()
        periodicity = str(request.data.get("periodicity", item.periodicity)).upper()
        distance_km = request.data.get("distance_km", item.distance_km)
        if not name or distance_km in (None, ""):
            return Response({"error": "name e distance_km sao obrigatorios"}, status=status.HTTP_400_BAD_REQUEST)
        if periodicity not in {"DIARIO", "SEMANAL", "QUINZENAL", "MENSAL"}:
            return Response({"error": "periodicity invalida"}, status=status.HTTP_400_BAD_REQUEST)

        item.name = name
        item.periodicity = periodicity
        item.distance_km = distance_km
        item.has_paid_parking = parse_bool(request.data.get("has_paid_parking", item.has_paid_parking))
        item.parking_cost = request.data.get("parking_cost") or 0
        item.save()
        return Response({"message": "Destino atualizado"}, status=status.HTTP_200_OK)

    def delete(self, request, destination_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            item = user.vehicle_destinations.get(id=destination_id)
        except VehicleFrequentDestination.DoesNotExist:
            return Response({"error": "Destino nao encontrado"}, status=status.HTTP_404_NOT_FOUND)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TripPlanListView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        data = user.trip_plans.select_related("vehicle").all().order_by("-created_at")
        return Response(
            [
                {
                    "id": t.id,
                    "vehicle_id": t.vehicle_id,
                    "vehicle_name": t.vehicle.name,
                    "title": t.title,
                    "date": t.date.strftime("%Y-%m-%d") if t.date else None,
                    "distance_km": t.distance_km,
                    "lodging_cost": t.lodging_cost,
                    "meal_cost": t.meal_cost,
                    "extra_cost": t.extra_cost,
                    "tolls": [{"id": x.id, "name": x.name, "amount": x.amount} for x in t.tolls.all()],
                }
                for t in data
            ]
        )


@method_decorator(csrf_exempt, name="dispatch")
class TripPlanCreateView(APIView):
    def post(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        vehicle_id = request.data.get("vehicle_id")
        try:
            vehicle = user.vehicles.get(id=vehicle_id)
        except Vehicle.DoesNotExist:
            return Response({"error": "Veiculo nao encontrado"}, status=status.HTTP_404_NOT_FOUND)

        trip = TripPlan.objects.create(
            user=user,
            vehicle=vehicle,
            title=str(request.data.get("title", "")).strip(),
            date=request.data.get("date") or None,
            distance_km=request.data.get("distance_km") or 0,
            lodging_cost=request.data.get("lodging_cost") or 0,
            meal_cost=request.data.get("meal_cost") or 0,
            extra_cost=request.data.get("extra_cost") or 0,
        )
        tolls = request.data.get("tolls") or []
        for item in tolls:
            TripToll.objects.create(
                trip=trip,
                name=str((item or {}).get("name", "")).strip(),
                amount=(item or {}).get("amount") or 0,
            )
        analysis = evaluate_trip_payload(
            user,
            {
                "vehicle_id": vehicle_id,
                "distance_km": trip.distance_km,
                "lodging_cost": trip.lodging_cost,
                "meal_cost": trip.meal_cost,
                "extra_cost": trip.extra_cost,
                "tolls": tolls,
            },
        )
        return Response({"message": "Viagem criada", "id": trip.id, "analysis": analysis}, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class TripPlanDetailView(APIView):
    def put(self, request, trip_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            trip = user.trip_plans.get(id=trip_id)
        except TripPlan.DoesNotExist:
            return Response({"error": "Viagem nao encontrada"}, status=status.HTTP_404_NOT_FOUND)

        vehicle_id = request.data.get("vehicle_id") or trip.vehicle_id
        try:
            trip.vehicle = user.vehicles.get(id=vehicle_id)
        except Vehicle.DoesNotExist:
            return Response({"error": "Veiculo nao encontrado"}, status=status.HTTP_404_NOT_FOUND)

        trip.title = str(request.data.get("title", trip.title)).strip()
        trip.date = request.data.get("date") or None
        trip.distance_km = request.data.get("distance_km") or 0
        trip.lodging_cost = request.data.get("lodging_cost") or 0
        trip.meal_cost = request.data.get("meal_cost") or 0
        trip.extra_cost = request.data.get("extra_cost") or 0
        trip.save()

        if "tolls" in request.data:
            trip.tolls.all().delete()
            for item in request.data.get("tolls") or []:
                TripToll.objects.create(
                    trip=trip,
                    name=str((item or {}).get("name", "")).strip(),
                    amount=(item or {}).get("amount") or 0,
                )

        analysis = evaluate_trip_payload(
            user,
            {
                "vehicle_id": trip.vehicle_id,
                "distance_km": trip.distance_km,
                "lodging_cost": trip.lodging_cost,
                "meal_cost": trip.meal_cost,
                "extra_cost": trip.extra_cost,
                "tolls": [{"name": x.name, "amount": float(x.amount or 0)} for x in trip.tolls.all()],
            },
        )
        return Response({"message": "Viagem atualizada", "analysis": analysis}, status=status.HTTP_200_OK)

    def delete(self, request, trip_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            trip = user.trip_plans.get(id=trip_id)
        except TripPlan.DoesNotExist:
            return Response({"error": "Viagem nao encontrada"}, status=status.HTTP_404_NOT_FOUND)
        trip.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_exempt, name="dispatch")
class TripEvaluateView(APIView):
    def post(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        analysis = evaluate_trip_payload(user, request.data)
        if analysis.get("error"):
            return Response(analysis, status=status.HTTP_400_BAD_REQUEST)
        return Response(analysis)


class VehicleSummaryView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        today = timezone.now().date()
        try:
            month = int(request.query_params.get("month", today.month))
        except ValueError:
            month = today.month
        try:
            year = int(request.query_params.get("year", today.year))
        except ValueError:
            year = today.year

        vehicles = list(user.vehicles.all())
        recurring_expenses = user.vehicle_expenses.filter(is_recurring=True)
        month_expenses = user.vehicle_expenses.filter(date__year=year, date__month=month, is_recurring=False)

        by_category = {
            "COMBUSTIVEL": 0,
            "MANUTENCAO": 0,
            "SEGURO": 0,
            "PEDAGIO": 0,
            "ESTACIONAMENTO": 0,
            "OUTRO": 0,
            "DESLOCAMENTO": 0,
            "DOCUMENTACAO": 0,
            "IPVA": 0,
            "LICENCIAMENTO": 0,
            "FINANCIAMENTO": 0,
        }

        vehicle_totals = []
        monthly_total = 0
        for v in vehicles:
            base_doc = float(v.documentation_cost or 0) / 12
            base_ipva = float(v.ipva_cost or 0) / 12
            base_lic = float(v.licensing_cost or 0) / 12
            financing = float(v.financing_installment_value or 0) if int(v.financing_remaining_installments or 0) > 0 else 0

            recurrent_total = sum(float(e.amount or 0) for e in recurring_expenses.filter(vehicle=v))
            month_total = sum(float(e.amount or 0) for e in month_expenses.filter(vehicle=v))
            destinations = user.vehicle_destinations.filter(vehicle=v)
            monthly_km = 0.0
            monthly_parking = 0.0
            for d in destinations:
                occ = destination_occurrences_per_month(d.periodicity)
                monthly_km += float(d.distance_km or 0) * occ
                if d.has_paid_parking:
                    monthly_parking += float(d.parking_cost or 0) * occ
            fuel_km_per_liter = float(v.fuel_km_per_liter or 0)
            fuel_price_per_liter = float(v.fuel_price_per_liter or 0)
            commute_fuel_cost = (monthly_km / fuel_km_per_liter) * fuel_price_per_liter if fuel_km_per_liter > 0 else 0.0
            commute_monthly_cost = commute_fuel_cost + monthly_parking

            vehicle_monthly_total = base_doc + base_ipva + base_lic + financing + recurrent_total + month_total + commute_monthly_cost
            monthly_total += vehicle_monthly_total

            by_category["DOCUMENTACAO"] += base_doc
            by_category["IPVA"] += base_ipva
            by_category["LICENCIAMENTO"] += base_lic
            by_category["FINANCIAMENTO"] += financing
            by_category["DESLOCAMENTO"] += commute_monthly_cost
            for e in recurring_expenses.filter(vehicle=v):
                by_category[e.expense_type] += float(e.amount or 0)
            for e in month_expenses.filter(vehicle=v):
                by_category[e.expense_type] += float(e.amount or 0)

            vehicle_totals.append(
                {
                    "vehicle_id": v.id,
                    "name": v.name,
                    "monthly_cost": round(vehicle_monthly_total, 2),
                    "commute_monthly_cost": round(commute_monthly_cost, 2),
                    "commute_fuel_cost": round(commute_fuel_cost, 2),
                    "commute_parking_cost": round(monthly_parking, 2),
                    "monthly_km": round(monthly_km, 2),
                    "fipe_value": float(v.fipe_value or 0),
                    "fipe_variation_percent": float(v.fipe_variation_percent or 0),
                    "financing_remaining_installments": int(v.financing_remaining_installments or 0),
                }
            )

        category_rows = [
            {"category": k, "total": round(val, 2)}
            for k, val in by_category.items()
            if val > 0
        ]
        category_rows.sort(key=lambda x: x["total"], reverse=True)
        vehicle_totals.sort(key=lambda x: x["monthly_cost"], reverse=True)
        commute_total = sum(v["commute_monthly_cost"] for v in vehicle_totals)

        return Response(
            {
                "month": month,
                "year": year,
                "monthly_total": round(monthly_total, 2),
                "commute_monthly_cost": round(commute_total, 2),
                "vehicle_count": len(vehicles),
                "by_category": category_rows,
                "vehicle_totals": vehicle_totals,
            }
        )


class CreditCardListView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        cards = list(user.credit_cards.select_related("parent_card").all().order_by("-created_at"))
        cards_by_id = {c.id: c for c in cards}
        return Response(
            [
                {
                    "id": c.id,
                    "nickname": c.nickname,
                    "last4": c.last4,
                    "parent_card_id": c.parent_card_id,
                    "parent_card_last4": c.parent_card.last4 if c.parent_card else None,
                    "closing_day": c.closing_day,
                    "due_day": c.due_day,
                    "best_purchase_day": c.best_purchase_day,
                    "limit_amount": c.limit_amount,
                    "miles_per_point": c.miles_per_point,
                    "billing_owner_id": get_owner_id_for_card(c, cards_by_id),
                }
                for c in cards
            ]
        )


@method_decorator(csrf_exempt, name="dispatch")
class CreditCardCreateView(APIView):
    def post(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        last4 = "".join(ch for ch in str(request.data.get("last4", "")) if ch.isdigit())
        try:
            closing_day = int(request.data.get("closing_day") or 0)
            due_day = int(request.data.get("due_day") or 0)
            best_purchase_day = int(request.data.get("best_purchase_day") or closing_day or 1)
        except (TypeError, ValueError):
            return Response({"error": "Fechamento e vencimento devem ser números válidos"}, status=status.HTTP_400_BAD_REQUEST)
        if closing_day < 1 or closing_day > 31:
            return Response({"error": "Fechamento deve estar entre 1 e 31"}, status=status.HTTP_400_BAD_REQUEST)
        if len(last4) != 4:
            return Response({"error": "Informe os 4 últimos dígitos do cartão"}, status=status.HTTP_400_BAD_REQUEST)
        if due_day < 1 or due_day > 31:
            return Response({"error": "Vencimento deve estar entre 1 e 31"}, status=status.HTTP_400_BAD_REQUEST)
        if best_purchase_day < 1 or best_purchase_day > 31:
            best_purchase_day = closing_day
        parent_card_id = request.data.get("parent_card_id")
        parent_card = None
        if parent_card_id not in (None, "", "null"):
            try:
                parent_card = user.credit_cards.get(id=parent_card_id)
            except CreditCard.DoesNotExist:
                return Response({"error": "Cartão principal não encontrado"}, status=status.HTTP_404_NOT_FOUND)

        card = CreditCard.objects.create(
            user=user,
            parent_card=parent_card,
            nickname=str(request.data.get("nickname", "")).strip(),
            last4=last4,
            closing_day=closing_day,
            due_day=due_day,
            best_purchase_day=best_purchase_day,
            limit_amount=request.data.get("limit_amount") or 0,
            miles_per_point=request.data.get("miles_per_point") or 1,
        )
        return Response({"message": "Cartão criado", "id": card.id}, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class CreditCardDetailView(APIView):
    def put(self, request, card_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            card = user.credit_cards.get(id=card_id)
        except CreditCard.DoesNotExist:
            return Response({"error": "Cartão não encontrado"}, status=status.HTTP_404_NOT_FOUND)

        last4 = "".join(ch for ch in str(request.data.get("last4", card.last4)) if ch.isdigit())
        try:
            closing_day = int(request.data.get("closing_day") or card.closing_day)
            due_day = int(request.data.get("due_day") or card.due_day)
            best_purchase_day = int(request.data.get("best_purchase_day") or closing_day)
        except (TypeError, ValueError):
            return Response({"error": "Fechamento e vencimento devem ser números válidos"}, status=status.HTTP_400_BAD_REQUEST)
        if closing_day < 1 or closing_day > 31:
            return Response({"error": "Fechamento deve estar entre 1 e 31"}, status=status.HTTP_400_BAD_REQUEST)
        if len(last4) != 4:
            return Response({"error": "Informe os 4 últimos dígitos do cartão"}, status=status.HTTP_400_BAD_REQUEST)
        if due_day < 1 or due_day > 31:
            return Response({"error": "Vencimento deve estar entre 1 e 31"}, status=status.HTTP_400_BAD_REQUEST)
        if best_purchase_day < 1 or best_purchase_day > 31:
            best_purchase_day = closing_day
        parent_card_id = request.data.get("parent_card_id")
        new_parent = None
        if parent_card_id not in (None, "", "null"):
            try:
                new_parent = user.credit_cards.get(id=parent_card_id)
            except CreditCard.DoesNotExist:
                return Response({"error": "Cartão principal não encontrado"}, status=status.HTTP_404_NOT_FOUND)
            if new_parent.id == card.id:
                return Response({"error": "Um cartão não pode herdar de si mesmo"}, status=status.HTTP_400_BAD_REQUEST)

            walk = new_parent
            seen = set()
            while walk and walk.parent_card_id and walk.id not in seen:
                if walk.parent_card_id == card.id:
                    return Response({"error": "Relação inválida de herança entre cartões"}, status=status.HTTP_400_BAD_REQUEST)
                seen.add(walk.id)
                walk = walk.parent_card

        old_owner = resolve_billing_owner(card)
        card.nickname = str(request.data.get("nickname", card.nickname)).strip()
        card.last4 = last4
        card.parent_card = new_parent
        card.closing_day = closing_day
        card.due_day = due_day
        card.best_purchase_day = best_purchase_day
        card.limit_amount = request.data.get("limit_amount") or 0
        card.miles_per_point = request.data.get("miles_per_point") or 1
        card.save()
        sync_credit_card_bills(user, card)
        if old_owner and old_owner.id != (resolve_billing_owner(card).id if resolve_billing_owner(card) else card.id):
            sync_credit_card_bills(user, old_owner)
        return Response({"message": "Cartão atualizado"}, status=status.HTTP_200_OK)

    def delete(self, request, card_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            card = user.credit_cards.get(id=card_id)
        except CreditCard.DoesNotExist:
            return Response({"error": "Cartão não encontrado"}, status=status.HTTP_404_NOT_FOUND)

        old_owner = resolve_billing_owner(card)
        child_ids = list(user.credit_cards.filter(parent_card=card).values_list("id", flat=True))
        user.planned_expenses.filter(source_key__startswith=f"CC:{card.id}:").delete()
        card.delete()
        if old_owner and old_owner.id != card.id:
            sync_credit_card_bills(user, old_owner)
        for child_id in child_ids:
            child = user.credit_cards.filter(id=child_id).first()
            if child:
                sync_credit_card_bills(user, child)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CreditCardExpenseListView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        data = user.credit_card_expenses.select_related("card").all().order_by("-date", "-id")
        card_id = request.query_params.get("card_id")
        if card_id:
            data = data.filter(card_id=card_id)
        return Response(
            [
                {
                    "id": e.id,
                    "card_id": e.card_id,
                    "card_last4": e.card.last4,
                    "card_name": e.card.nickname or f"****{e.card.last4}",
                    "date": e.date.strftime("%Y-%m-%d"),
                    "category": e.category,
                    "description": e.description,
                    "amount": e.amount,
                }
                for e in data
            ]
        )


@method_decorator(csrf_exempt, name="dispatch")
class CreditCardExpenseCreateView(APIView):
    def post(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        card_id = request.data.get("card_id")
        date = request.data.get("date")
        category = str(request.data.get("category", "")).strip()
        amount = request.data.get("amount")
        if not card_id or not date or not category or amount in (None, ""):
            return Response(
                {"error": "card_id, date, category e amount são obrigatórios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            card = user.credit_cards.get(id=card_id)
        except CreditCard.DoesNotExist:
            return Response({"error": "Cartão não encontrado"}, status=status.HTTP_404_NOT_FOUND)

        expense = CreditCardExpense.objects.create(
            user=user,
            card=card,
            date=date,
            category=category,
            description=request.data.get("description", "") or "",
            amount=amount,
        )
        sync_credit_card_bills(user, card)
        return Response({"message": "Gasto no cartão criado", "id": expense.id}, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class CreditCardExpenseDetailView(APIView):
    def put(self, request, expense_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            expense = user.credit_card_expenses.get(id=expense_id)
        except CreditCardExpense.DoesNotExist:
            return Response({"error": "Gasto não encontrado"}, status=status.HTTP_404_NOT_FOUND)

        old_card = expense.card
        card_id = request.data.get("card_id") or expense.card_id
        try:
            card = user.credit_cards.get(id=card_id)
        except CreditCard.DoesNotExist:
            return Response({"error": "Cartão não encontrado"}, status=status.HTTP_404_NOT_FOUND)

        date = request.data.get("date")
        category = str(request.data.get("category", "")).strip()
        amount = request.data.get("amount")
        if not date or not category or amount in (None, ""):
            return Response(
                {"error": "date, category e amount são obrigatórios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        expense.card = card
        expense.date = date
        expense.category = category
        expense.description = request.data.get("description", "") or ""
        expense.amount = amount
        expense.save()

        sync_credit_card_bills(user, card)
        if old_card.id != card.id:
            sync_credit_card_bills(user, old_card)
        return Response({"message": "Gasto no cartão atualizado"}, status=status.HTTP_200_OK)

    def delete(self, request, expense_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        try:
            expense = user.credit_card_expenses.get(id=expense_id)
        except CreditCardExpense.DoesNotExist:
            return Response({"error": "Gasto não encontrado"}, status=status.HTTP_404_NOT_FOUND)

        card = expense.card
        expense.delete()
        sync_credit_card_bills(user, card)
        return Response(status=status.HTTP_204_NO_CONTENT)


class CreditCardSummaryView(APIView):
    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        today = timezone.now().date()
        try:
            month = int(request.query_params.get("month", today.month))
        except ValueError:
            month = today.month
        try:
            year = int(request.query_params.get("year", today.year))
        except ValueError:
            year = today.year

        cards = list(user.credit_cards.select_related("parent_card").all())
        cards_by_id = {c.id: c for c in cards}
        all_expenses = user.credit_card_expenses.select_related("card").all()
        owner_limit_map = {}
        owner_card_map = {}
        for card in cards:
            owner_id = get_owner_id_for_card(card, cards_by_id)
            owner_card = cards_by_id.get(owner_id, card)
            owner_card_map[owner_id] = owner_card
            owner_limit_map[owner_id] = float(owner_card.limit_amount or 0)
        total_limit = sum(owner_limit_map.values())
        total_spent = 0.0

        by_category = defaultdict(float)
        by_card = defaultdict(float)
        by_billing = defaultdict(float)
        points_total = 0.0
        points_brl_base = 0.0
        usd_brl_quote = fetch_usd_brl_quote()
        effective_rate = float((usd_brl_quote or {}).get("rate") or 0)
        for expense in all_expenses:
            owner_id = get_owner_id_for_card(expense.card, cards_by_id)
            owner_card = owner_card_map.get(owner_id, expense.card)
            _, _, _, comp_year, comp_month = card_invoice_period_and_due(owner_card, expense.date)
            if comp_year != year or comp_month != month:
                continue
            total_spent += float(expense.amount or 0)
            by_category[expense.category] += float(expense.amount or 0)
            by_card[f"****{expense.card.last4}"] += float(expense.amount or 0)
            by_billing[owner_id] += float(expense.amount or 0)
            amount_brl = float(expense.amount or 0)
            points_per_usd = float(expense.card.miles_per_point or 0)
            points_brl_base += amount_brl * points_per_usd
            if effective_rate > 0:
                points_total += (amount_brl / effective_rate) * points_per_usd

        by_category_rows = [{"category": k, "total": round(v, 2)} for k, v in by_category.items()]
        by_category_rows.sort(key=lambda x: x["total"], reverse=True)
        by_card_rows = [{"card": k, "total": round(v, 2)} for k, v in by_card.items()]
        by_card_rows.sort(key=lambda x: x["total"], reverse=True)
        by_billing_rows = []
        for owner_id in owner_limit_map.keys():
            used = by_billing.get(owner_id, 0.0)
            owner = owner_card_map.get(owner_id)
            if not owner:
                continue
            members = [
                c for c in cards
                if get_owner_id_for_card(c, cards_by_id) == owner_id
            ]
            by_billing_rows.append(
                {
                    "owner_card_id": owner_id,
                    "owner_name": owner.nickname or f"Cartão {owner.last4}",
                    "owner_last4": owner.last4,
                    "limit_amount": round(float(owner.limit_amount or 0), 2),
                    "used_amount": round(float(used), 2),
                    "used_percent": round((float(used) / float(owner.limit_amount or 1)) * 100, 2) if float(owner.limit_amount or 0) > 0 else 0,
                    "member_cards": [
                        {
                            "id": c.id,
                            "nickname": c.nickname,
                            "last4": c.last4,
                        }
                        for c in members
                    ],
                }
            )
        by_billing_rows.sort(key=lambda x: x["used_amount"], reverse=True)

        upcoming = user.planned_expenses.filter(
            source_key__startswith="CC:",
            date__year=year,
            date__month=month,
        ).order_by("date")
        upcoming_rows = [
            {
                "id": p.id,
                "date": p.date.strftime("%Y-%m-%d"),
                "category": p.category,
                "amount": p.amount,
                "is_paid": p.is_paid,
            }
            for p in upcoming
        ]

        return Response(
            {
                "month": month,
                "year": year,
                "card_count": len(cards),
                "total_spent": round(total_spent, 2),
                "total_limit": round(total_limit, 2),
                "usage_percent": round((total_spent / total_limit) * 100, 2) if total_limit > 0 else 0,
                "usd_brl_rate": round(effective_rate, 4) if effective_rate > 0 else None,
                "usd_brl_timestamp": (usd_brl_quote or {}).get("timestamp"),
                "usd_brl_create_date": (usd_brl_quote or {}).get("create_date"),
                "usd_brl_name": (usd_brl_quote or {}).get("name"),
                "usd_brl_source": (usd_brl_quote or {}).get("source"),
                "points_brl_base": round(points_brl_base, 4),
                "estimated_points": round(points_total, 2),
                "estimated_miles": round(points_total, 2),
                "by_category": by_category_rows,
                "by_card": by_card_rows,
                "by_billing": by_billing_rows,
                "upcoming_bills": upcoming_rows,
            }
        )


@method_decorator(csrf_exempt, name="dispatch")
class PlannerCreateView(APIView):
    def post(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        date = request.data.get("date")
        category = request.data.get("category")
        amount = request.data.get("amount")

        if not date or not category or amount in (None, ""):
            return Response(
                {"error": "date, category e amount sao obrigatorios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        planned = PlannedExpense.objects.create(
            user=user,
            date=date,
            category=category,
            description=request.data.get("description", ""),
            amount=amount,
            is_recurring=parse_bool(request.data.get("is_recurring", False)),
            is_paid=parse_bool(request.data.get("is_paid", False)),
        )

        return Response(
            {
                "message": "Despesa fixa criada",
                "id": planned.id,
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name="dispatch")
class PlannedIncomeCreateView(APIView):
    def post(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        date = request.data.get("date")
        category = request.data.get("category")
        amount = request.data.get("amount")

        if not date or not category or amount in (None, ""):
            return Response(
                {"error": "date, category e amount sao obrigatorios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        planned = PlannedIncome.objects.create(
            user=user,
            date=date,
            category=category,
            description=request.data.get("description", ""),
            amount=amount,
            is_recurring=parse_bool(request.data.get("is_recurring", False)),
        )

        return Response(
            {
                "message": "Entrada fixa criada",
                "id": planned.id,
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name="dispatch")
class PlannedReserveCreateView(APIView):
    def post(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        date = request.data.get("date")
        category = request.data.get("category")
        amount = request.data.get("amount")

        if not date or not category or amount in (None, ""):
            return Response(
                {"error": "date, category e amount sao obrigatorios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        planned = PlannedReserve.objects.create(
            user=user,
            date=date,
            category=category,
            description=request.data.get("description", ""),
            amount=amount,
            is_recurring=parse_bool(request.data.get("is_recurring", False)),
        )

        return Response(
            {
                "message": "Reserva criada",
                "id": planned.id,
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name="dispatch")
class PlannerDetailView(APIView):
    def put(self, request, expense_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            planned = user.planned_expenses.get(id=expense_id)
        except PlannedExpense.DoesNotExist:
            return Response(
                {"error": "Despesa fixa nao encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        date = request.data.get("date")
        category = request.data.get("category")
        amount = request.data.get("amount")

        if not date or not category or amount in (None, ""):
            return Response(
                {"error": "date, category e amount sao obrigatorios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        planned.date = date
        planned.category = category
        planned.description = request.data.get("description", "")
        planned.amount = amount
        planned.is_recurring = parse_bool(request.data.get("is_recurring", False))
        planned.is_paid = parse_bool(request.data.get("is_paid", False))
        planned.save()

        return Response({"message": "Despesa fixa atualizada"}, status=status.HTTP_200_OK)

    def delete(self, request, expense_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            planned = user.planned_expenses.get(id=expense_id)
        except PlannedExpense.DoesNotExist:
            return Response(
                {"error": "Despesa fixa nao encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        planned.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_exempt, name="dispatch")
class PlannedIncomeDetailView(APIView):
    def put(self, request, income_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            planned = user.planned_incomes.get(id=income_id)
        except PlannedIncome.DoesNotExist:
            return Response(
                {"error": "Entrada fixa nao encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        date = request.data.get("date")
        category = request.data.get("category")
        amount = request.data.get("amount")

        if not date or not category or amount in (None, ""):
            return Response(
                {"error": "date, category e amount sao obrigatorios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        planned.date = date
        planned.category = category
        planned.description = request.data.get("description", "")
        planned.amount = amount
        planned.is_recurring = parse_bool(request.data.get("is_recurring", False))
        planned.save()

        return Response({"message": "Entrada fixa atualizada"}, status=status.HTTP_200_OK)

    def delete(self, request, income_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            planned = user.planned_incomes.get(id=income_id)
        except PlannedIncome.DoesNotExist:
            return Response(
                {"error": "Entrada fixa nao encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        planned.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_exempt, name="dispatch")
class PlannedReserveDetailView(APIView):
    def put(self, request, reserve_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            planned = user.planned_reserves.get(id=reserve_id)
        except PlannedReserve.DoesNotExist:
            return Response(
                {"error": "Reserva nao encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        date = request.data.get("date")
        category = request.data.get("category")
        amount = request.data.get("amount")

        if not date or not category or amount in (None, ""):
            return Response(
                {"error": "date, category e amount sao obrigatorios"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        planned.date = date
        planned.category = category
        planned.description = request.data.get("description", "")
        planned.amount = amount
        planned.is_recurring = parse_bool(request.data.get("is_recurring", False))
        planned.save()

        return Response({"message": "Reserva atualizada"}, status=status.HTTP_200_OK)

    def delete(self, request, reserve_id):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        try:
            planned = user.planned_reserves.get(id=reserve_id)
        except PlannedReserve.DoesNotExist:
            return Response(
                {"error": "Reserva nao encontrada"},
                status=status.HTTP_404_NOT_FOUND,
            )

        planned.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class StatsBaseView(APIView):
    delta_days = 1

    def get(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        start_date = timezone.now().date() - timedelta(days=self.delta_days - 1)

        qs = FinancialEntry.objects.filter(user=user, date__gte=start_date)

        total_receita = qs.filter(entry_type="RECEITA").aggregate(total=Sum("amount"))["total"] or 0
        total_despesa = qs.filter(entry_type="DESPESA").aggregate(total=Sum("amount"))["total"] or 0
        movimentacoes = qs.count()

        total = total_receita + total_despesa or 1

        percent_receita = round((total_receita / total) * 100)
        percent_despesa = round((total_despesa / total) * 100)

        return Response(
            {
                "total_receita": total_receita,
                "total_despesa": total_despesa,
                "movimentacoes": movimentacoes,
                "percent_receita": percent_receita,
                "percent_despesa": percent_despesa,
            }
        )


class DailyStatsView(StatsBaseView):
    delta_days = 1


class WeeklyStatsView(StatsBaseView):
    delta_days = 7


class MonthlyStatsView(StatsBaseView):
    delta_days = 30


class WhatsAppSummaryWebhookView(APIView):
    def post(self, request):
        user = get_logged_user(request)
        if not user:
            return Response(status=status.HTTP_401_UNAUTHORIZED)

        text = str(request.data.get("text", "")).strip()
        if not text:
            return Response(
                {"error": "text e obrigatorio"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        outbound = {
            "phone_number": user.phone_number,
            "text": text,
        }

        mode = str(request.data.get("mode", "prod")).strip().lower()
        if user.phone_number != "5511913305093":
            mode = "prod"
        if mode == "dev":
            webhook_url = "https://n8n.lowcodeforward.com/webhook-test/genfinWpp"
        else:
            webhook_url = "https://n8n.lowcodeforward.com/webhook/genfinWpp"
        req = urllib_request.Request(
            webhook_url,
            data=json.dumps(outbound).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib_request.urlopen(req, timeout=12) as resp:
                webhook_status = resp.getcode()
        except Exception as exc:
            return Response(
                {"error": "Falha ao enviar para webhook", "detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {"message": "Resumo enviado", "webhook_status": webhook_status, "mode": mode},
            status=status.HTTP_200_OK,
        )


