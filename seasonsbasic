import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import pytz

# 1. 페이지 설정
st.set_page_config(page_title="Seasons Basic (Andy)", page_icon="🌿", layout="wide")
KST = pytz.timezone('Asia/Seoul')

# --- 데이터 엔진 ---
@st.cache_data(ttl=3600)
def get_data(ticker, start_date):
    try:
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
        st.error(f"데이터 오류: {e}")
        return None

# --- 시뮬레이션 엔진 ---
def run_simulation(df, initial_seed, start_limit_date, end_limit_date=None):
    sim_df = df[df.index.date >= start_limit_date].copy()
    if end_limit_date:
        sim_df = sim_df[sim_df.index.date <= end_limit_date]
        
    if sim_df.empty: return pd.DataFrame(), []

    boxx_rate = (1 + 0.05) ** (1/252) - 1 
    cash_a = initial_seed * 0.5  
    cash_b = initial_seed * 0.5  
    
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
        
        # 계절(모드) 판단: Ivy(상승), Lily(하락)
        weights = [2, 1, 2] if curr_c >= ma120 else [1, 2, 3]
        
        if shares > 0 and curr_c >= s_l:
            cash_b += shares * curr_c
            shares, buy_count, avg_price = 0, 0, 0.0
            if pending_rebalance:
                total = cash_a + cash_b
                cash_a, cash_b = total * 0.5, total * 0.5
                pending_rebalance = False
        
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
with st.sidebar:
    st.header("⚙️ 전략 설정")
    ticker = st.text_input("대상 종목", value="SOXL")
    init_seed = st.number_input("투자 원금 ($)", value=10000)
    st.divider()
    st.info("💡 **Andy 원칙**\n1. 현금 5:5 고정\n2. 120일선 가변분할\n3. 연간 조건부 리밸런싱")

tab1, tab2 = st.tabs(["🎯 실시간 현황 & 가이드", "📊 과거 백테스트 상세"])

# 데이터 로드
raw_df = get_data(ticker, date(2013, 1, 1)) # 충분한 과거 데이터 로드

with tab1:
    op_start = st.date_input("운용 시작일 (수익률 계산 기준)", value=date(2024, 1, 1))
    if raw_df is not None:
        res_live = run_simulation(raw_df, init_seed, op_start)
        if not res_live.empty:
            cur = res_live.iloc[-1]
            latest = raw_df.iloc[-1]
            
            # 현황 위젯
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("현재 총 자산", f"${cur['Total']:,.2f}")
            m2.metric("누적 수익률", f"{(cur['Total']/init_seed-1)*100:+.2f}%")
            m3.metric("채워진 슬롯", f"{int(cur['Shares'] > 0) * (res_live['Shares'].diff().ne(0).cumsum().iloc[-1] % 4)} / 3") # 간략화된 슬롯 표시
            m4.metric("안전 자산(BOXX)", f"${cur['Cash_A']:,.2f}")

            st.divider()
            
            # 계절(모드) 가이드
            x_val = latest['x']
            is_ivy = latest['close'] >= latest['ma120']
            mode_name = "🌿 Ivy (아이비)" if is_ivy else "🌸 Lily (릴리)"
            mode_color = "green" if is_ivy else "blue"
            
            st.subheader(f"오늘의 계절: :{mode_color}[{mode_name}]")
            st.caption(f"120일선(${latest['ma120']:.2f}) 기준 {'상승' if is_ivy else '하락'} 추세입니다.")
            
            g1, g2 = st.columns(2)
            with g1:
                st.error("📥 매수 가이드 (LOC)")
                b_p = round(x_val * 0.99, 2)
                if cur['Shares'] == 0:
                    w = [2, 1, 2] if is_ivy else [1, 2, 3]
                    qty = (cur['Cash_B'] * (w[0]/sum(w))) // b_p
                    st.write(f"**타점:** `${b_p}` 이하 | **수량:** `{int(qty)} 주` (1차)")
                else: st.write("추가 매수 조건 확인 필요")
                
            with g2:
                st.info("📤 매도 가이드 (LOC)")
                s_p = round(x_val * 1.01, 2)
                if cur['Shares'] > 0:
                    st.write(f"**타점:** `${s_p}` 이상 | **수량:** `{int(cur['Shares'])} 주` (전량)")
                else: st.write("보유 물량 없음")

            st.line_chart(res_live['Total'])

with tab2:
    st.header("📊 전략 성적표 (Backtest)")
    col1, col2 = st.columns(2)
    bt_start = col1.date_input("테스트 시작", value=date(2013, 1, 1))
    bt_end = col2.date_input("테스트 종료", value=date.today())
    
    if st.button("🚀 백테스트 실행"):
        res_bt = run_simulation(raw_df, init_seed, bt_start, bt_end)
        if not res_bt.empty:
            # 주요 지표 계산
            f_val = res_bt['Total'].iloc[-1]
            days = (res_bt.index[-1] - res_bt.index[0]).days
            cagr = ((f_val / init_seed) ** (365.25 / days) - 1) * 100
            
            peak = res_bt['Total'].cummax()
            mdd_series = (res_bt['Total'] - peak) / peak
            mdd = mdd_series.min() * 100
            calmar = cagr / abs(mdd) if mdd != 0 else 0
            
            # 지표 출력
            i1, i2, i3, i4 = st.columns(4)
            i1.metric("최종 자산", f"${f_val:,.0f}")
            i2.metric("CAGR (연복리)", f"{cagr:.2f}%")
            i3.metric("최대 낙폭 (MDD)", f"{mdd:.2f}%")
            i4.metric("Calmar 지수", f"{calmar:.2f}")
            
            st.line_chart(res_bt['Total'])
            
            # 연도별 통계
            res_bt['Year'] = res_bt.index.year
            y_stats = []
            for yr, group in res_bt.groupby('Year'):
                y_ret = (group['Total'].iloc[-1] / group['Total'].iloc[0] - 1) * 100
                y_mdd = ((group['Total'] - group['Total'].cummax()) / group['Total'].cummax()).min() * 100
                y_stats.append({"연도": yr, "수익률": f"{y_ret:+.2f}%", "MDD": f"{y_mdd:.2f}%"})
            
            st.subheader("📅 연도별 상세 성적")
            st.table(pd.DataFrame(y_stats))
