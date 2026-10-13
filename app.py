"""GrowthOS: dashboard de marketing analytics (dados 100% sintéticos)."""
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

DATA = Path(__file__).parent / "data"
GOOD, BAD, MUTED = "#4ADE80", "#F87171", "#8a8a8a"
COLORS = ["#e6e6e6", "#4ea1d3", "#d98c4a", "#6fbf8b", "#c76f8f", "#8c8cc7", "#b0b0b0", "#7d7d7d"]

st.set_page_config(page_title="GrowthOS | Marketing Analytics", layout="wide")
st.markdown(
    """
<style>
.block-container {padding-top: 3rem; padding-bottom: 1rem; max-width: 100%;}
header[data-testid="stHeader"] {height: 0;}
div[data-testid="stMetric"] {background:#121212; border:1px solid #2a2a2a; padding:10px 12px; border-radius:0;}
div[data-testid="stMetricLabel"] p {font-size:.72rem; color:#9a9a9a; text-transform:uppercase; letter-spacing:.06em;}
div[data-testid="stMetricValue"] {font-size:1.05rem; white-space:nowrap;}
div[data-testid="stMetricDelta"] {font-size:.75rem;}
h1 {font-size:1.5rem !important; padding:0 0 .2rem 0 !important;}
h3 {font-size:.95rem !important; font-weight:600 !important; text-transform:uppercase; letter-spacing:.06em; color:#cfcfcf;}
button[data-baseweb="tab"] {border-radius:0;}
* {border-radius:0 !important;}
</style>
""",
    unsafe_allow_html=True,
)


# ---------- formatação pt-BR ----------
def _ptbr(s: str) -> str:
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def brl(v, compact=True):
    if pd.isna(v):
        return "—"
    a = abs(v)
    if compact and a >= 1e6:
        return _ptbr(f"R$ {v / 1e6:.1f} mi")
    if compact and a >= 1e3:
        return _ptbr(f"R$ {v / 1e3:.0f} mil")
    return _ptbr(f"R$ {v:,.0f}")


def num(v):
    return "—" if pd.isna(v) else _ptbr(f"{v:,.0f}")


def pct(v, d=1):
    return "—" if pd.isna(v) else _ptbr(f"{v * 100:.{d}f}%")


def delta(cur, prev):
    if prev is None or not prev or pd.isna(prev):
        return None
    return _ptbr(f"{(cur / prev - 1) * 100:+.1f}%")


def style(fig, h=300, legend=True):
    fig.update_layout(
        template="plotly_dark", height=h, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=8, r=8, t=8, b=8), font=dict(size=11, color="#cfcfcf"), showlegend=legend,
        legend=dict(orientation="h", y=1.12, x=0, font=dict(size=10)), colorway=COLORS,
    )
    fig.update_xaxes(gridcolor="#1f1f1f", zeroline=False)
    fig.update_yaxes(gridcolor="#1f1f1f", zeroline=False)
    return fig


# ---------- dados ----------
@st.cache_data(show_spinner="Carregando base...")
def load():
    rd = lambda n: pd.read_csv(DATA / f"{n}.csv")
    ch, rg, pr = rd("dim_channel"), rd("dim_region"), rd("dim_product")
    cu, me, od = rd("dim_customer"), rd("fact_media_daily"), rd("fact_orders")
    it, tg, ex = rd("fact_order_items"), rd("fact_targets_monthly"), rd("fact_experiments_weekly")
    to_date = lambda s: pd.to_datetime(s.astype(str), format="%Y%m%d")
    od["date"], me["date"] = to_date(od.date_id), to_date(me.date_id)
    od["valid"] = od.order_status != "Cancelado"  # cancelado: receita 0, fora de pedidos e CAC
    od = od.merge(ch[["channel_id", "channel", "media_type"]], on="channel_id").merge(
        rg[["region_id", "state", "macro_region"]], on="region_id")
    me = me.merge(ch[["channel_id", "channel", "media_type"]], on="channel_id")
    cu["acquisition_date"] = pd.to_datetime(cu.acquisition_date)
    tg["month"] = pd.to_datetime(tg.target_month_id.astype(str), format="%Y%m")
    it = it.merge(pr[["product_id", "category"]], on="product_id")
    return dict(ch=ch, od=od[od.valid].copy(), od_all=od, me=me, cu=cu, it=it, tg=tg, ex=ex)


D = load()
MIN, MAX = D["od"].date.min().date(), D["od"].date.max().date()

# ---------- filtros ----------
with st.sidebar:
    st.markdown("## GrowthOS")
    st.caption("Marketing analytics · e-commerce multicanal · dados 100% sintéticos")
    rng = st.date_input("Período", value=(MIN, MAX), min_value=MIN, max_value=MAX, format="DD/MM/YYYY")
    if len(rng) != 2:
        st.stop()
    d0, d1 = pd.Timestamp(rng[0]), pd.Timestamp(rng[1])
    names = D["ch"].channel.tolist()
    sel = st.multiselect("Canais", names, default=names)
    if not sel:
        st.warning("Selecione ao menos um canal.")
        st.stop()
    ids = D["ch"][D["ch"].channel.isin(sel)].channel_id.tolist()
    st.divider()
    st.caption(
        "ROAS e CAC são calculados só para mídia paga. Pedidos cancelados ficam de fora. "
        "Devolvidos reconhecem 25% da receita. Detalhes na aba Metodologia."
    )

n_days = (d1 - d0).days + 1
p1 = d0 - pd.Timedelta(days=1)
p0 = p1 - pd.Timedelta(days=n_days - 1)
has_prev = p0 >= pd.Timestamp(MIN)


def slice_(df, a, b):
    return df[(df.date >= a) & (df.date <= b) & df.channel_id.isin(ids)]


o, m = slice_(D["od"], d0, d1), slice_(D["me"], d0, d1)
o_prev, m_prev = (slice_(D["od"], p0, p1), slice_(D["me"], p0, p1)) if has_prev else (None, None)


def kpis(o_, m_):
    rev, spend, new = o_.net_revenue.sum(), m_.spend.sum(), o_.new_customer_flag.sum()
    paid_new = o_[o_.media_type == "Pago"].new_customer_flag.sum()
    paid_spend = m_[m_.media_type == "Pago"].spend.sum()
    return dict(
        rev=rev, margin=o_.gross_margin.sum(), spend=spend, orders=len(o_), new=new,
        roas=rev / spend if spend else np.nan,
        cac=paid_spend / paid_new if paid_new else np.nan,
        aov=rev / len(o_) if len(o_) else np.nan,
        mrate=o_.gross_margin.sum() / rev if rev else np.nan,
    )


K = kpis(o, m)
P = kpis(o_prev, m_prev) if has_prev else {}
g = lambda k: P.get(k)

st.title("Performance de marketing")
st.caption(f"{d0:%d/%m/%Y} a {d1:%d/%m/%Y} · {len(sel)} de {len(names)} canais"
           + (f" · variação vs. {p0:%d/%m/%Y} a {p1:%d/%m/%Y}" if has_prev else " · sem período anterior para comparar"))

cols = st.columns(8)
cols[0].metric("Receita", brl(K["rev"]), delta(K["rev"], g("rev")))
cols[1].metric("Margem bruta", pct(K["mrate"]), delta(K["mrate"], g("mrate")))
cols[2].metric("Investimento", brl(K["spend"]), delta(K["spend"], g("spend")), delta_color="off")
cols[3].metric("ROAS", _ptbr(f"{K['roas']:.1f}x") if pd.notna(K["roas"]) else "—", delta(K["roas"], g("roas")))
cols[4].metric("CAC (pago)", brl(K["cac"], False), delta(K["cac"], g("cac")), delta_color="inverse")
cols[5].metric("Pedidos", num(K["orders"]), delta(K["orders"], g("orders")))
cols[6].metric("Ticket médio", brl(K["aov"], False), delta(K["aov"], g("aov")))
cols[7].metric("Novos clientes", num(K["new"]), delta(K["new"], g("new")))

t1, t2, t3, t4, t5 = st.tabs(["Visão geral", "Canais", "Clientes", "Experimentos", "Metodologia"])

# ================= VISÃO GERAL =================
with t1:
    mo = o.groupby(o.date.dt.to_period("M").dt.to_timestamp()).agg(rev=("net_revenue", "sum"), margin=("gross_margin", "sum"))
    mm = m.groupby(m.date.dt.to_period("M").dt.to_timestamp()).spend.sum()
    mo = mo.join(mm).fillna(0)
    mo["roas"] = np.where(mo.spend > 0, mo.rev / mo.spend, np.nan)

    a, b = st.columns([3, 2])
    with a:
        st.markdown("### Receita, investimento e ROAS por mês")
        f = go.Figure()
        f.add_bar(x=mo.index, y=mo.rev, name="Receita líquida", marker_color="#3a3a3a")
        f.add_bar(x=mo.index, y=mo.spend, name="Investimento", marker_color=COLORS[1])
        f.add_scatter(x=mo.index, y=mo.roas, name="ROAS (eixo direito)", yaxis="y2", mode="lines+markers",
                      line=dict(color="#fff", width=2), marker=dict(size=5))
        f.update_layout(barmode="group", yaxis=dict(title="R$"), yaxis2=dict(title="ROAS (x)", overlaying="y", side="right", showgrid=False))
        st.plotly_chart(style(f, 310), width="stretch")
    with b:
        st.markdown("### Realizado vs. meta de receita")
        tg = D["tg"][D["tg"].channel_id.isin(ids)]
        tg = tg[(tg.month >= d0.to_period("M").to_timestamp()) & (tg.month <= d1.to_period("M").to_timestamp())]
        tgm = tg.groupby("month").target_net_revenue.sum()
        cmp_ = pd.DataFrame({"Realizado": mo.rev, "Meta": tgm}).dropna()
        att = cmp_.Realizado.sum() / cmp_.Meta.sum() if len(cmp_) else np.nan
        f = go.Figure()
        f.add_scatter(x=cmp_.index, y=cmp_.Meta, name="Meta", line=dict(color=MUTED, dash="dot"))
        f.add_scatter(x=cmp_.index, y=cmp_.Realizado, name="Realizado", line=dict(color="#fff", width=2), fill="tonexty", fillcolor="rgba(255,255,255,.06)")
        st.plotly_chart(style(f, 260), width="stretch")
        st.caption(f"Atingimento da meta no período: **{pct(att)}**")

    a, b, c = st.columns(3)
    with a:
        st.markdown("### Receita por praça")
        r = o.groupby("state").net_revenue.sum().sort_values()
        st.plotly_chart(style(go.Figure(go.Bar(x=r.values, y=r.index, orientation="h", marker_color="#e6e6e6")), 320, False), width="stretch")
    with b:
        st.markdown("### Categoria: receita e margem")
        itf = D["it"][D["it"].order_id.isin(o.order_id)]
        cat = itf.groupby("category").agg(rev=("net_revenue", "sum"), mar=("item_margin", "sum"))
        cat["mrate"] = cat.mar / cat.rev
        cat = cat.sort_values("rev")
        f = px.bar(cat, x="rev", y=cat.index, orientation="h", color="mrate", color_continuous_scale=["#2a2a2a", "#e6e6e6"],
                   labels={"rev": "Receita (R$)", "mrate": "Margem", "category": "", "y": ""})
        f.update_coloraxes(colorbar=dict(title="Margem", tickformat=".0%", len=.8))
        st.plotly_chart(style(f, 320, False), width="stretch")
    with c:
        st.markdown("### Pedidos por status (base completa)")
        oa = D["od_all"]
        oa = oa[(oa.date >= d0) & (oa.date <= d1) & oa.channel_id.isin(ids)]
        s = oa.order_status.value_counts()
        f = go.Figure(go.Pie(labels=s.index, values=s.values, hole=.6, marker=dict(colors=["#e6e6e6", "#7d7d7d", BAD]), textinfo="label+percent"))
        st.plotly_chart(style(f, 320, False), width="stretch")

# ================= CANAIS =================
with t2:
    ch = o.groupby(["channel", "media_type"]).agg(rev=("net_revenue", "sum"), mar=("gross_margin", "sum"), orders=("order_id", "count"), new=("new_customer_flag", "sum")).reset_index()
    sp = m.groupby("channel").spend.sum()
    ch["spend"] = ch.channel.map(sp).fillna(0)
    paid = ch.media_type == "Pago"
    ch["roas"] = np.where(paid & (ch.spend > 0), ch.rev / ch.spend.replace(0, np.nan), np.nan)
    ch["cac"] = np.where(paid & (ch.new > 0), ch.spend / ch.new.replace(0, np.nan), np.nan)
    ch["contrib"] = ch.mar - ch.spend
    ch["mrate"] = ch.mar / ch.rev
    ch["share"] = ch.rev / ch.rev.sum() * 100
    ch = ch.sort_values("rev", ascending=False)
    paid = ch.media_type == "Pago"

    st.markdown("### Economia por canal")
    st.dataframe(
        ch.rename(columns={"channel": "Canal", "media_type": "Tipo", "spend": "Investimento (R$)", "rev": "Receita (R$)", "roas": "ROAS", "cac": "CAC (R$)",
                           "mrate": "Margem %", "contrib": "Margem após mídia (R$)", "orders": "Pedidos", "share": "% da receita"})
          [["Canal", "Tipo", "Investimento (R$)", "Receita (R$)", "% da receita", "ROAS", "CAC (R$)", "Margem %", "Margem após mídia (R$)", "Pedidos"]],
        hide_index=True, width="stretch",
        column_config={
            "Investimento (R$)": st.column_config.NumberColumn(format="compact"),
            "Receita (R$)": st.column_config.NumberColumn(format="compact"),
            "% da receita": st.column_config.ProgressColumn(format="%.1f%%", min_value=0, max_value=float(ch.share.max())),
            "ROAS": st.column_config.NumberColumn(format="%.1fx"),
            "CAC (R$)": st.column_config.NumberColumn(format="%.0f"),
            "Margem %": st.column_config.NumberColumn(format="percent"),
            "Margem após mídia (R$)": st.column_config.NumberColumn(format="compact"),
            "Pedidos": st.column_config.NumberColumn(format="%d"),
        },
    )
    st.caption("ROAS e CAC só existem para mídia paga. Canais próprios e orgânicos aparecem apenas com receita e margem.")

    a, b, c = st.columns([3, 2, 3])
    with a:
        st.markdown("### Investimento vs. ROAS (mídia paga)")
        pp = ch[paid & (ch.spend > 0)]
        f = px.scatter(pp, x="spend", y="roas", size="rev", text="channel", color="mrate", color_continuous_scale=["#4a4a4a", "#e6e6e6"], size_max=40,
                       labels={"spend": "Investimento (R$)", "roas": "ROAS (x)", "mrate": "Margem"})
        f.update_traces(textposition="top center")
        f.update_coloraxes(colorbar=dict(title="Margem", tickformat=".0%", len=.8))
        st.plotly_chart(style(f, 320, False), width="stretch")
    with b:
        st.markdown("### Funil de mídia")
        fn = m[["impressions", "clicks", "sessions", "add_to_carts", "checkouts"]].sum()
        vals = fn.tolist() + [len(o)]
        f = go.Figure(go.Funnel(y=["Impressões", "Cliques", "Sessões", "Carrinhos", "Checkouts", "Pedidos"], x=vals, text=[_ptbr(f"{v/1e6:.1f} mi") if v >= 1e6 else _ptbr(f"{v:,.0f}") for v in vals], textinfo="text+percent previous",
                                marker=dict(color=["#e6e6e6", "#c4c4c4", "#9a9a9a", "#7d7d7d", "#5e5e5e", "#4ea1d3"])))
        st.plotly_chart(style(f, 320, False), width="stretch")
    with c:
        st.markdown("### Mix de receita por canal")
        mix = o.groupby([o.date.dt.to_period("M").dt.to_timestamp().rename("mes"), "channel"]).net_revenue.sum().reset_index()
        f = px.area(mix, x="mes", y="net_revenue", color="channel", labels={"net_revenue": "Receita", "mes": "", "channel": ""})
        st.plotly_chart(style(f, 320), width="stretch")

# ================= CLIENTES =================
with t3:
    cu = D["cu"]
    cs = cu[cu.acquisition_channel_id.isin(ids) & (cu.acquisition_date >= d0) & (cu.acquisition_date <= d1)].copy()
    cs["cohort"] = cs.acquisition_date.dt.to_period("M")

    a, b = st.columns([3, 2])
    with a:
        st.markdown("### Retenção por coorte de aquisição (% de clientes que compraram)")
        ov = D["od"][D["od"].customer_id.isin(cs.customer_id)][["customer_id", "date"]].merge(cs[["customer_id", "cohort"]], on="customer_id")
        ov["off"] = (ov.date.dt.year - ov.cohort.dt.year) * 12 + (ov.date.dt.month - ov.cohort.dt.month)
        act = ov[ov.off.between(1, 12)].groupby(["cohort", "off"]).customer_id.nunique().unstack()
        size = cs.groupby("cohort").size()
        ret = act.reindex(size.index).div(size, axis=0)
        ret = ret.reindex(columns=range(1, 13))
        end = pd.Period(D["od"].date.max(), "M")
        for cohort in ret.index:  # meses ainda não observados ficam vazios
            for k in ret.columns:
                if cohort + k > end:
                    ret.loc[cohort, k] = np.nan
        ret.index = ret.index.strftime("%m/%y")
        f = px.imshow(ret * 100, text_auto=".1f", aspect="auto", color_continuous_scale=[[0, "#141414"], [1, "#e6e6e6"]],
                      labels=dict(x="Meses após a aquisição", y="Coorte", color="%"))
        f.update_coloraxes(showscale=False)
        f.update_traces(textfont_size=9)
        st.plotly_chart(style(f, 480, False), width="stretch")
    with b:
        st.markdown("### Receita: novos vs. recorrentes")
        nr = o.assign(tipo=np.where(o.new_customer_flag == 1, "Novos", "Recorrentes")).groupby(
            [o.date.dt.to_period("M").dt.to_timestamp().rename("mes"), "tipo"]).net_revenue.sum().reset_index()
        f = px.bar(nr, x="mes", y="net_revenue", color="tipo", color_discrete_map={"Novos": COLORS[1], "Recorrentes": "#e6e6e6"}, labels={"net_revenue": "Receita", "mes": "", "tipo": ""})
        st.plotly_chart(style(f, 230), width="stretch")
        st.markdown("### Receita por cliente (vida inteira) por canal de aquisição")
        ltv = cs.merge(D["ch"][["channel_id", "channel"]], left_on="acquisition_channel_id", right_on="channel_id").groupby("channel").net_revenue_lifetime.mean().sort_values()
        st.plotly_chart(style(go.Figure(go.Bar(x=ltv.values, y=ltv.index, orientation="h", marker_color="#e6e6e6")), 230, False), width="stretch")

    a, b = st.columns(2)
    with a:
        st.markdown("### Receita por cliente por faixa etária")
        s = cs.groupby("age_band").net_revenue_lifetime.mean()
        st.plotly_chart(style(go.Figure(go.Bar(x=s.index, y=s.values, marker_color="#9a9a9a")), 240, False), width="stretch")
    with b:
        st.markdown("### Receita por cliente por faixa de renda")
        s = cs.groupby("income_tier").net_revenue_lifetime.mean().sort_values()
        st.plotly_chart(style(go.Figure(go.Bar(x=s.index, y=s.values, marker_color="#9a9a9a")), 240, False), width="stretch")

# ================= EXPERIMENTOS =================
with t4:
    ex = D["ex"][D["ex"].channel_id.isin(ids)]
    rows = []
    for (eid, name, chid), g_ in ex.groupby(["experiment_id", "experiment", "channel_id"]):
        v = g_.groupby(["experiment_group", "period"])[["visitors", "orders"]].sum()
        tp, tq, cp, cq = v.loc[("Teste", "Pré")], v.loc[("Teste", "Pós")], v.loc[("Controle", "Pré")], v.loc[("Controle", "Pós")]
        r = lambda x: x.orders / x.visitors
        rr = (r(tq) / r(tp)) / (r(cq) / r(cp))
        se = np.sqrt(sum(1 / x.orders - 1 / x.visitors for x in (tp, tq, cp, cq)))
        lo, hi = np.exp(np.log(rr) - 1.96 * se) - 1, np.exp(np.log(rr) + 1.96 * se) - 1
        incr = tq.orders - tq.visitors * r(tp) * (r(cq) / r(cp))
        spend = g_.media_spend.sum()
        status = "Significativo (+)" if lo > 0 else ("Significativo (−)" if hi < 0 else "Inconclusivo")
        rows.append(dict(Experimento=name, Canal=D["ch"].set_index("channel_id").channel[chid], Lift=rr - 1, IC_inf=lo, IC_sup=hi,
                         Incrementais=incr, Investimento=spend, CustoPorIncremental=spend / incr if incr > 0 and spend > 0 else np.nan, Leitura=status))
    E = pd.DataFrame(rows).sort_values("Lift")

    a, b = st.columns([2, 3])
    with a:
        st.markdown("### Lift incremental com IC 95%")
        f = go.Figure()
        f.add_vline(x=0, line_color=MUTED, line_dash="dot")
        f.add_scatter(x=E.Lift * 100, y=E.Experimento, mode="markers", marker=dict(size=9, color=["#fff" if s_ == "Inconclusivo" else GOOD if "(+)" in s_ else BAD for s_ in E.Leitura]),
                      error_x=dict(type="data", symmetric=False, array=(E.IC_sup - E.Lift) * 100, arrayminus=(E.Lift - E.IC_inf) * 100, color=MUTED))
        f.update_xaxes(title="Lift (%)")
        st.plotly_chart(style(f, 300, False), width="stretch")
    with b:
        st.markdown("### Resultados")
        st.dataframe(
            E.sort_values("Lift", ascending=False)[["Experimento", "Canal", "Lift", "IC_inf", "IC_sup", "Incrementais", "CustoPorIncremental", "Leitura"]]
             .rename(columns={"IC_inf": "IC 95% inf.", "IC_sup": "IC 95% sup.", "Incrementais": "Pedidos incrementais", "CustoPorIncremental": "Custo/pedido incr."}),
            hide_index=True, width="stretch",
            column_config={"Lift": st.column_config.NumberColumn(format="percent"), "IC 95% inf.": st.column_config.NumberColumn(format="percent"),
                           "IC 95% sup.": st.column_config.NumberColumn(format="percent"), "Pedidos incrementais": st.column_config.NumberColumn(format="%d"),
                           "Custo/pedido incr.": st.column_config.NumberColumn(format="R$ %.0f")},
        )
    st.caption("Diferença-em-diferenças sobre a taxa de conversão (pedidos / visitantes), teste vs. controle, antes e depois. "
               "O intervalo usa aproximação normal do log da razão de taxas. Leitura 'Inconclusivo' = o intervalo inclui zero. "
               "Os experimentos têm janelas fixas e não dependem do filtro de período.")

# ================= METODOLOGIA =================
with t5:
    st.markdown(
        """
**Base.** 100% sintética (seed fixa), 2024–2025, e-commerce multicanal no Brasil: 54,5 mil pedidos, 28,7 mil clientes, 8 canais e 12 praças, em modelo estrela.

**Definições**
- **Receita líquida:** `net_revenue` dos pedidos, sem cancelados (receita zero) e com 25% da receita dos devolvidos.
- **Margem bruta:** receita menos CMV, frete e taxa de pagamento. **Margem após mídia:** margem bruta menos investimento do canal.
- **ROAS:** receita líquida do canal (último toque) dividida pelo investimento, apenas para mídia paga. O ROAS do topo é o *blended* (receita total / investimento total do filtro).
- **CAC (pago):** investimento em mídia paga dividido pelos novos clientes vindos de canais pagos.
- **Retenção:** % dos clientes de cada coorte de aquisição com ao menos um pedido não cancelado no mês indicado.
- **Experimentos:** diferença-em-diferenças com IC 95%; ver nota na aba.

**Limites.** A atribuição é por último toque. O investimento não é aberto por praça, então a visão regional mostra só receita. Por ser sintética, a base não permite conclusões de negócio reais.
"""
    )
