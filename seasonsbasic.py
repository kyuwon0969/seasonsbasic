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
                
                # 기존 MDD (전고점 대비 최대 낙폭)
                mdd = ((res_bt['Total'] - peak) / peak).min() * 100
                
                # 추가: 원금 대비 최대 손실률 (Max Loss from Principal)
                # 원금보다 자산이 낮아졌을 때의 최소값을 찾고 비율 계산 (원금보다 항상 높으면 0.0)
                max_loss_principal = min((res_bt['Total'].min() - init_seed) / init_seed * 100, 0.0)
                
                calmar = cagr / abs(mdd) if mdd != 0 else 0
                
                # 결과 지표 출력 (컬럼을 5개로 늘려 배치)
                k1, k2, k3, k4, k5 = st.columns(5)
                k1.metric("최종 결과", f"${f_val:,.0f}")
                k2.metric("CAGR (연복리)", f"{cagr:.2f}%")
                k3.metric("MDD (고점대비)", f"{mdd:.2f}%")
                k4.metric("원금대비 최대손실", f"{max_loss_principal:.2f}%")
                k5.metric("Calmar (수익 효율)", f"{calmar:.2f}")
                
                st.subheader("📅 연도별 성과 통계")
                res_bt['Year'] = res_bt.index.year
                y_stats = []
                for yr, group in res_bt.groupby('Year'):
                    y_ret = (group['Total'].iloc[-1] / group['Total'].iloc[0] - 1) * 100
                    y_mdd = ((group['Total'] - group['Total'].cummax()) / group['Total'].cummax()).min() * 100
                    y_stats.append({"연도": yr, "수익률": f"{y_ret:+.2f}%", "MDD": f"{y_mdd:.2f}%"})
                st.table(pd.DataFrame(y_stats))
                st.line_chart(res_bt['Total'])
