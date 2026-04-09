import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import pytz

# 1. 페이지 설정
st.set_page_config(page_title="Seasons Basic (Andy)", page_icon="🌙", layout="wide")
KST = pytz.timezone('Asia/Seoul')

# --- 데이터 엔진 (데이터만 깨끗하게 가져옵니다) ---
@st.cache_data(ttl=3600)
def get_data(ticker, start_date):
    try:
        fetch_start = pd.to_datetime(start_date) - pd.DateOffset(months=10)
        fetch_end = date.today() + timedelta(days=1)
        data = yf.download(ticker, start=fetch_start, end=fetch_end, progress=False)
        if data.empty: return None
        
        df = pd.DataFrame(index=data.index)
        if isinstance(data.columns, pd.MultiIndex):
            df['close'] = data['Close'][ticker].ffill()
        else:
            df['close'] = data['Close'].ffill()
        
        # 120일선만 미리 계산 (참조용)
        df['ma120'] = df['close'].rolling(window=120).mean()
        return df.dropna()
    except Exception as e:
        st.error(f"⚠️ 데이터 엔진 오류: {e}")
        return None

# --- 시뮬레이션 엔진 (참조 로직 수정) ---
def run_simulation(df, initial_seed, start_limit_date, end_limit_date=None):
    last_available_date = df.index[-1].date()
    actual_start_date = min(start_limit_date, last_available_date)
    
    # 시뮬레이션 대상 데이터 필터링
    sim_df = df[df.index.date >= actual_start_date].copy()
    if end_limit_date:
        sim_df = sim_df[sim_df.index.date <= end_limit_date]
    if sim_df.empty: return pd.DataFrame(), False

    boxx_rate = (1 + 0.05) ** (1/252) - 1 
    cash_a = initial_seed * 0.5 
    cash_b = initial_seed * 0.5 
    shares, buy_count, avg_price = 0, 0, 0.0
    history = []
    
    last_year = sim_df.index[0].year
    pending_rebalance = False
    rebalanced_today = False 

    for i, (date_idx, row) in enumerate(sim_df.iterrows()):
        rebalanced_today = False
        if date_idx.year != last_year:
            pending_rebalance = True
            last_year = date_idx.year

        # [중요 수정] 현재 행(i)을 기준으로 원본 df에서 정확히 어제(i-1)와 전전날(i-2)을 찾습니다.
        # 루프를 도는 sim_df가 아니라 전체 데이터가 담긴 df에서 위치를 찾아야 오차가 없습니다.
        current_pos = df.index.get_loc(date_idx)
        p1_close = df['close'].iloc[current_pos - 1] # 어제 종가
        p2_close = df['close'].iloc[current_pos - 2] # 전전날 종가
        
        curr_c = float(row['close'])
        ma120 = float(row['ma120'])
        
        # 기준가 x = (어제 종가 + 전전날 종가) / 2
        x = round((p1_close + p2_close) / 2, 2)
        
        b_l = round(x * 0.99, 2) 
        s_l = round(x * 1.01, 2) 
        weights = [2, 1, 2] if curr_c >= ma120 else [1, 2, 3]
        
        if shares > 0 and curr_c >= s_l:
            cash_b += shares * curr_c
            shares, buy_count, avg_price = 0, 0, 0.0
            if pending_rebalance:
                total = cash_a + cash_b
                cash_a, cash_b = total * 0.5, total * 0.5
                pending_rebalance = False
                rebalanced_today = True 
        
        elif buy_count < 3 and curr_c <= b_l:
            rem_w = sum(weights[buy_count:])
            curr_w = weights[buy_count]
            buy_money = cash_b * (curr_w / rem_w)
            buy_qty = buy_money // b_l
            if buy_qty > 0:
                cost = buy_qty * curr_c
                avg_price = ((avg_price * shares) + cost) / (shares + buy_qty)
                shares += buy_qty
                cash_b -= cost
                buy_count += 1

        if i == 0:
            total_assets = initial_seed
        else:
            cash_a *= (1 + boxx_rate)
            total_assets = cash_a + cash_b + (shares * curr_c)

        history.append({
            'Date': date_idx, 'Total': total_assets, 'Cash_A': cash_a, 
            'Cash_B': cash_b, 'Shares': shares, 'Avg': avg_price,
            'Rebalanced': rebalanced_today, 'x': x # x값 확인용 추가
        })

    return pd.DataFrame(history).set_index('Date'), rebalanced_today

# --- UI 레이아웃 ---
st.title("🌿 Seasons Basic : Sun & Moon")
st.markdown("58년 개띠 형님을 위한 **정확한 종가 참조** 투자 계산기")

with st.sidebar:
    st.header("⚙️ 운용 설정")
    ticker = st.text_input("분석 종목", value="SOXL")
    init_seed = st.number_input("시작 원금 ($)", value=10000, step=1000)
    st.divider()
    st.write("📌 **전략 요약**")
    st.write("- 자산 비중: 5:5 고정\n- 리밸런싱: 1년 주기(익절 시)\n- 추세 필터: 120일 이동평균선")

tab1, tab2 = st.tabs(["🎯 오늘의 가이드", "📊 백테스트 리포트"])

with tab1:
    op_start = st.date_input("운용 시작일 (주문 가이드 기준)", value=date.today())
    raw_df_live = get_data(ticker, op_start)
    
    boxx_data = yf.download("BOXX", period="5d", progress=False)
    boxx_price = 100.0
    if not boxx_data.empty:
        temp_close = boxx_data['Close']
        boxx_price = temp_close.iloc[:, 0].ffill().iloc[-1] if isinstance(temp_close, pd.DataFrame) else temp_close.ffill().iloc[-1]

    if raw_df_live is not None:
        res_live, is_reb = run_simulation(raw_df_live, init_seed, op_start)
        if not res_live.empty:
            cur = res_live.iloc[-1]
            # [수정] 가장 최근 확정 데이터(어제/전전날) 가져오기
            p1_final = raw_df_live['close'].iloc[-1]
            p2_final = raw_df_live['close'].iloc[-2]
            final_x = round((p1_final + p2_final) / 2, 2)
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("총 자산 가치", f"${cur['Total']:,.2f}")
            col2.metric("누적 수익률", f"{(cur['Total']/init_seed-1)*100:+.2f}%")
            col3.metric("금고(BOXX) 현금", f"${cur['Cash_A']:,.2f}")
            col4.metric("매수 대기 자금", f"${cur['Cash_B']:,.2f}")
            st.divider()
            
            if op_start >= date.today() - timedelta(days=3) or is_reb:
                title = "🛡️ 안전자산(BOXX) 매매 가이드"
                if is_reb: title = "🔄 연간 리밸런싱: BOXX 매매 가이드"
                st.subheader(title)
                b1, b2 = st.columns([1, 2])
                with b1:
                    try:
                        target_boxx_qty = float(cur['Cash_A']) // float(boxx_price)
                        st.warning(f"**현재 보유해야 할 BOXX: `{int(target_boxx_qty)} 주`**")
                        st.write(f"(최근 종가기준: `${float(boxx_price):.2f}`)")
                    except: st.warning("**수량 계산 중...**")
                with b2:
                    st.info("> BOXX는 시장가로 매수하며, 1년에 한 번만 리밸런싱합니다.")
                st.divider()

            # --- Sun/Moon 가이드 (수정된 final_x 적용) ---
            ma120_val = raw_df_live['ma120'].iloc[-1]
            is_sun = raw_df_live['close'].iloc[-1] >= ma120_val
            mode_name, mode_color = ("☀️ 양지 (Sun Mode)", "orange") if is_sun else ("🌙 음지 (Moon Mode)", "blue")
            st.subheader(f"현재 기운: :{mode_color}[{mode_name}]")
            st.caption(f"참조: 어제(${p1_final:.2f}) + 전전날(${p2_final:.2f}) 평균 | 120일선: ${ma120_val:.2f}")
            
            g1, g2 = st.columns(2)
            with g1:
                st.error("📥 내일의 매수 타점 (LOC)")
                b_p = round(final_x * 0.99, 2)
                if cur['Shares'] == 0:
                    w = [2, 1, 2] if is_sun else [1, 2, 3]
                    qty = (cur['Cash_B'] * (w[0]/sum(w))) // b_p
                    st.write(f"**가격:** `${b_p}` 이하 | **수량:** `{int(qty)} 주` (1차)")
                else:
                    buy_history = res_live['Shares'].diff()
                    current_slots = int(len(buy_history[buy_history > 0]) % 4)
                    st.write(f"**현재 {current_slots if current_slots > 0 else 3}차 매수 완료.**")
            with g2:
                st.info("📤 내일의 매도 타점 (LOC)")
                s_p = round(final_x * 1.01, 2)
                if cur['Shares'] > 0:
                    st.write(f"**가격:** `${s_p}` 이상 | **수량:** `{int(cur['Shares'])} 주` (전량)")
                else: st.write("보유 중인 주식이 없습니다.")
            st.line_chart(res_live['Total'])

# [백테스트 탭은 시뮬레이션 엔진 수정을 통해 자동으로 정확해졌습니다]
with tab2:
    st.header("📊 백테스트 리포트 (Backtest)")
    bt1, bt2 = st.columns(2)
    min_date, max_date = date(2013, 1, 1), date(2030, 12, 31)
    bt_start = bt1.date_input("분석 시작일 선택", value=date(2013, 1, 1), min_value=min_date, max_value=max_date)
    bt_end = bt2.date_input("분석 종료일 선택", value=date.today(), min_value=min_date, max_value=max_date)
    
    if st.button("🚀 상세 분석 시작"):
        raw_df_bt = get_data(ticker, bt_start)
        if raw_df_bt is not None:
            res_bt, _ = run_simulation(raw_df_bt, init_seed, bt_start, bt_end)
            if not res_bt.empty:
                f_val, days = res_bt['Total'].iloc[-1], (res_bt.index[-1] - res_bt.index[0]).days
                cagr = ((f_val / init_seed) ** (365.25 / max(days, 1)) - 1) * 100
                peak = res_bt['Total'].cummax()
                mdd = ((res_bt['Total'] - peak) / peak).min() * 100
                calmar = cagr / abs(mdd) if mdd != 0 else 0
                k1, k2, k3, k4 = st.columns(4)
                k1.metric("최종 결과", f"${f_val:,.0f}"); k2.metric("CAGR (연복리)", f"{cagr:.2f}%")
                k3.metric("MDD (최대낙폭)", f"{mdd:.2f}%"); k4.metric("Calmar (수익 효율)", f"{calmar:.2f}")
                
                st.subheader("📅 연도별 성과 통계")
                res_bt['Year'] = res_bt.index.year
                y_stats = []
                for yr, group in res_bt.groupby('Year'):
                    y_ret = (group['Total'].iloc[-1] / group['Total'].iloc[0] - 1) * 100
                    y_mdd = ((group['Total'] - group['Total'].cummax()) / group['Total'].cummax()).min() * 100
                    y_stats.append({"연도": yr, "수익률": f"{y_ret:+.2f}%", "MDD": f"{y_mdd:.2f}%"})
                st.table(pd.DataFrame(y_stats))
                st.line_chart(res_bt['Total'])
