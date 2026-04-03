import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import pytz

# 1. 페이지 설정
st.set_page_config(page_title="Seasons Basic (Andy)", page_icon="🌙", layout="wide")
KST = pytz.timezone('Asia/Seoul')

# --- 데이터 엔진 ---
@st.cache_data(ttl=3600)
def get_data(ticker, start_date):
    try:
        # 120일선 계산을 위해 8개월 전부터 데이터 로드
        fetch_start = pd.to_datetime(start_date) - pd.DateOffset(months=8)
        data = yf.download(ticker, start=fetch_start, progress=False)
        if data.empty: return None
        
        df = pd.DataFrame(index=data.index)
        if isinstance(data.columns, pd.MultiIndex):
            df['close'] = data['Close'][ticker].ffill()
        else:
            df['close'] = data['Close'].ffill()
            
        df['ma120'] = df['close'].rolling(window=120).mean()
        df['p1'] = df['close'].shift(1)
        df['p2'] = df['close'].shift(2)
        df['x'] = ((df['p1'] + df['p2']) / 2).round(2)
        
        return df.dropna()
    except Exception as e:
        st.error(f"⚠️ 데이터 엔진 오류: {e}")
        return None

# --- 시뮬레이션 엔진 ---
def run_simulation(df, initial_seed, start_limit_date, end_limit_date=None):
    sim_df = df[df.index.date >= start_limit_date].copy()
    if end_limit_date:
        sim_df = sim_df[sim_df.index.date <= end_limit_date]
        
    if sim_df.empty: return pd.DataFrame()

    boxx_rate = (1 + 0.05) ** (1/252) - 1 
    cash_a = initial_seed * 0.5  # 안전자산
    cash_b = initial_seed * 0.5  # 매매자금
    
    shares, buy_count, avg_price = 0, 0, 0.0
    history = []
    
    last_year = sim_df.index[0].year
    pending_rebalance = False

    for date, row in sim_df.iterrows():
        if date.year != last_year:
            pending_rebalance = True
            last_year = date.year

        curr_c = float(row['close'])
        ma120 = float(row['ma120'])
        x = float(row['x'])
        
        b_l = round(x * 0.99, 2) 
        s_l = round(x * 1.01, 2) 
        
        # Sun(상승) / Moon(하락) 모드 판별
        weights = [2, 1, 2] if curr_c >= ma120 else [1, 2, 3]
        
        # 익절 및 리밸런싱
        if shares > 0 and curr_c >= s_l:
            cash_b += shares * curr_c
            shares, buy_count, avg_price = 0, 0, 0.0
            if pending_rebalance:
                total = cash_a + cash_b
                cash_a, cash_b = total * 0.5, total * 0.5
                pending_rebalance = False
        
        # 분할 매수
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

        cash_a *= (1 + boxx_rate)
        total_assets = cash_a + cash_b + (shares * curr_c)
        history.append({'Date': date, 'Total': total_assets, 'Cash_A': cash_a, 'Cash_B': cash_b, 'Shares': shares, 'Avg': avg_price})

    return pd.DataFrame(history).set_index('Date')

# --- UI 레이아웃 ---
st.title("🌿 Seasons Basic : Sun & Moon")
st.markdown("58년 개띠 형님을 위한 **안전 자산 배분** 전략 계산기")

with st.sidebar:
    st.header("⚙️ 운용 설정")
    ticker = st.text_input("분석 종목", value="SOXL")
    init_seed = st.number_input("시작 원금 ($)", value=10000, step=1000)
    st.divider()
    st.write("📌 **전략 요약**")
    st.write("- 자산 비중: 5:5 고정")
    st.write("- 리밸런싱: 1년 주기(익절 시)")
    st.write("- 추세 필터: 120일 이동평균선")

tab1, tab2 = st.tabs(["🎯 오늘의 가이드", "📊 백테스트 리포트"])

# 데이터 로드
raw_df = get_data(ticker, date(2013, 1, 1))

with tab1:
    op_start = st.date_input("수익률 계산 시작일", value=date(2024, 1, 1))
    if raw_df is not None:
        res_live = run_simulation(raw_df, init_seed, op_start)
        if not res_live.empty:
            cur = res_live.iloc[-1]
            latest = raw_df.iloc[-1]
            
            # 현황판
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("총 자산 가치", f"${cur['Total']:,.2f}")
            col2.metric("누적 수익률", f"{(cur['Total']/init_seed-1)*100:+.2f}%")
            col3.metric("금고(BOXX) 현금", f"${cur['Cash_A']:,.2f}")
            col4.metric("매수 대기 자금", f"${cur['Cash_B']:,.2f}")

            st.divider()
            
            # Sun / Moon 모드 표시
            x_val = latest['x']
            is_sun = latest['close'] >= latest['ma120']
            mode_name = "☀️ 양지 (Sun Mode)" if is_sun else "🌙 음지 (Moon Mode)"
            mode_color = "orange" if is_sun else "blue"
            
            st.subheader(f"현재 기운: :{mode_color}[{mode_name}]")
            st.caption(f"120일선(${latest['ma120']:.2f}) 기준 {'상승' if is_sun else '하락'} 추세가 이어지고 있습니다.")
            
            g1, g2 = st.columns(2)
            with g1:
                st.error("📥 내일의 매수 타점 (LOC)")
                b_p = round(x_val * 0.99, 2)
                if cur['Shares'] == 0:
                    w = [2, 1, 2] if is_sun else [1, 2, 3]
                    qty = (cur['Cash_B'] * (w[0]/sum(w))) // b_p
                    st.write(f"**가격:** `${b_p}` 이하 | **수량:** `{int(qty)} 주` (1차)")
                else: 
                    st.write(f"**현재 {int(res_live['Shares'].diff().ne(0).cumsum().iloc[-1] % 4)}차 매수 완료.**")
                    st.write("익절 전까지 추가 매수 조건 대기 중입니다.")
                
            with g2:
                st.info("📤 내일의 매도 타점 (LOC)")
                s_p = round(x_val * 1.01, 2)
                if cur['Shares'] > 0:
                    st.write(f"**가격:** `${s_p}` 이상 | **수량:** `{int(cur['Shares'])} 주` (전량)")
                else: st.write("보유 중인 주식이 없습니다.")

            st.subheader("📈 자산 성장 곡선")
            st.line_chart(res_live['Total'])

with tab2:
    st.header("📊 백테스트 리포트 (Backtest)")
    bt1, bt2 = st.columns(2)
    bt_start = bt1.date_input("분석 시작일", value=date(2013, 1, 1))
    bt_end = bt2.date_input("분석 종료일", value=date.today())
    
    if st.button("🚀 상세 분석 시작"):
        res_bt = run_simulation(raw_df, init_seed, bt_start, bt_end)
        if not res_bt.empty:
            f_val = res_bt['Total'].iloc[-1]
            days = (res_bt.index[-1] - res_bt.index[0]).days
            cagr = ((f_val / init_seed) ** (365.25 / days) - 1) * 100
            
            peak = res_bt['Total'].cummax()
            mdd_series = (res_bt['Total'] - peak) / peak
            mdd = mdd_series.min() * 100
            calmar = cagr / abs(mdd) if mdd != 0 else 0
            
            # 핵심 지표 위젯
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("최종 결과", f"${f_val:,.0f}")
            k2.metric("CAGR (연복리)", f"{cagr:.2f}%")
            k3.metric("MDD (최대낙폭)", f"{mdd:.2f}%")
            k4.metric("Calmar (수익 효율)", f"{calmar:.2f}")
            
            st.subheader("📅 연도별 성과 통계")
            res_bt['Year'] = res_bt.index.year
            y_stats = []
            for yr, group in res_bt.groupby('Year'):
                y_ret = (group['Total'].iloc[-1] / group['Total'].iloc[0] - 1) * 100
                y_mdd = ((group['Total'] - group['Total'].cummax()) / group['Total'].cummax()).min() * 100
                y_stats.append({"연도": yr, "수익률": f"{y_ret:+.2f}%", "MDD": f"{y_mdd:.2f}%"})
            
            st.table(pd.DataFrame(y_stats))
            st.line_chart(res_bt['Total'])
