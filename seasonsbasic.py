import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
import pytz

# 1. 페이지 설정
st.set_page_config(page_title="Seasons Basic (Andy)", page_icon="🌙", layout="wide")

# --- 시간 설정 (한국 시간으로 강제 고정) ---
KST = pytz.timezone('Asia/Seoul')
def get_now_kst():
    return datetime.now(KST)

# --- 데이터 엔진 (TTL을 줄여서 더 자주 갱신하게 함) ---
@st.cache_data(ttl=600) # 10분마다 데이터 갱신 체크
def get_data(ticker, start_date):
    try:
        # 120일선 계산을 위해 10개월 전부터 로드
        fetch_start = pd.to_datetime(start_date) - pd.DateOffset(months=10)
        # 오늘 날짜를 한국 시간 기준으로 다시 계산
        today_val = get_now_kst().date()
        fetch_end = today_val + timedelta(days=1)
        
        data = yf.download(ticker, start=fetch_start, end=fetch_end, progress=False)
        if data.empty: return None
        
        df = pd.DataFrame(index=data.index)
        if isinstance(data.columns, pd.MultiIndex):
            df['close'] = data['Close'][ticker].ffill()
        else:
            df['close'] = data['Close'].ffill()
            
        df['ma120'] = df['close'].rolling(window=120).mean()
        return df.dropna()
    except Exception as e:
        st.error(f"⚠️ 데이터 엔진 오류: {e}")
        return None

# --- 시뮬레이션 엔진 ---
def run_simulation(df, initial_seed, start_limit_date, end_limit_date=None):
    last_available_date = df.index[-1].date()
    actual_start_date = min(start_limit_date, last_available_date)
    
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

        current_pos = df.index.get_loc(date_idx)
        p1_close = df['close'].iloc[current_pos - 1] 
        p2_close = df['close'].iloc[current_pos - 2] 
        
        curr_c = float(row['close'])
        ma120 = float(row['ma120'])
        
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

        if i == 0: total_assets = initial_seed
        else:
            cash_a *= (1 + boxx_rate)
            total_assets = cash_a + cash_b + (shares * curr_c)

        history.append({
            'Date': date_idx, 'Total': total_assets, 'Cash_A': cash_a, 
            'Cash_B': cash_b, 'Shares': shares, 'Avg': avg_price,
            'Rebalanced': rebalanced_today 
        })
    return pd.DataFrame(history).set_index('Date'), rebalanced_today

# --- UI 레이아웃 ---
# 오늘 날짜를 한국 시간 기준으로 정의
now_kst = get_now_kst()
today_kst = now_kst.date()

st.title("🌿 Seasons Basic : Sun & Moon")
st.markdown(f"58년 개띠 형님을 위한 **자동 날짜 갱신** 계산기 (현재 한국시간: {now_kst.strftime('%Y-%m-%d %H:%M')})")

with st.sidebar:
    st.header("⚙️ 운용 설정")
    ticker = st.text_input("분석 종목", value="SOXL")
    init_seed = st.number_input("시작 원금 ($)", value=10000, step=1000)
    st.divider()
    if st.button("🔄 데이터 강제 새로고침"):
        st.cache_data.clear()
        st.rerun()

tab1, tab2 = st.tabs(["🎯 오늘의 가이드", "📊 백테스트 리포트"])

with tab1:
    # 핵심 수정: value=today_kst 를 넣어 사이트를 열 때마다 오늘 날짜가 기본값이 됨
    op_start = st.date_input("운용 시작일 (주문 가이드 기준)", value=today_kst)
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
            latest_date = raw_df_live.index[-1]
            p1_final = raw_df_live['close'].iloc[-1] 
            p2_final = raw_df_live['close'].iloc[-2] 
            final_x = round((p1_final + p2_final) / 2, 2)
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("총 자산 가치", f"${cur['Total']:,.2f}")
            col2.metric("누적 수익률", f"{(cur['Total']/init_seed-1)*100:+.2f}%")
            col3.metric("금고(BOXX) 현금", f"${cur['Cash_A']:,.2f}")
            col4.metric("매수 대기 자금", f"${cur['Cash_B']:,.2f}")
            st.divider()
            
            # --- Sun/Moon 가이드 ---
            ma120_val = raw_df_live['ma120'].iloc[-1]
            is_sun = raw_df_live['close'].iloc[-1] >= ma120_val
            mode_name, mode_color = ("☀️ 양지 (Sun Mode)", "orange") if is_sun else ("🌙 음지 (Moon Mode)", "blue")
            
            st.subheader(f"현재 기운: :{mode_color}[{mode_name}]")
            st.caption(f"📅 **데이터 기준일: {latest_date.date()}** (미국 장 종료 기준)")
            st.write(f"👉 계산 근거: {latest_date.date()} 종가(`${p1_final:.2f}`) + 그 전날 종가(`${p2_final:.2f}`)의 평균")
            
            g1, g2 = st.columns(2)
            with g1:
                st.error("📥 내일의 매수 타점 (LOC)")
                b_p = round(final_x * 0.99, 2)
                if cur['Shares'] == 0:
                    w = [2, 1, 2] if is_sun else [1, 2, 3]
                    qty = (cur['Cash_B'] * (w[0]/sum(w))) // b_p
                    st.write(f"**타점:** `${b_p}` 이하 | **수량:** `{int(qty)} 주` (1차)")
                else:
                    st.write("보유 중입니다. 다음 분할 매수나 익절을 기다립니다.")
            with g2:
                st.info("📤 내일의 매도 타점 (LOC)")
                s_p = round(final_x * 1.01, 2)
                if cur['Shares'] > 0:
                    st.write(f"**타점:** `${s_p}` 이상 | **수량:** `{int(cur['Shares'])} 주` (전량)")
                else: st.write("보유 중인 주식이 없습니다.")
            st.line_chart(res_live['Total'])

with tab2:
    st.header("📊 백테스트 리포트 (Backtest)")
    bt1, bt2 = st.columns(2)
    min_date, max_date = date(2013, 1, 1), date(2030, 12, 31)
    bt_start = bt1.date_input("분석 시작일 선택", value=date(2013, 1, 1), min_value=min_date, max_value=max_date)
    bt_end = bt2.date_input("분석 종료일 선택", value=today_kst, min_value=min_date, max_value=max_date)
    
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
