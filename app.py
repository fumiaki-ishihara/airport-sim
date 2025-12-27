#!/usr/bin/env python3
"""
空港混雑シミュレーション Streamlit Webアプリ

Usage:
    streamlit run app.py
"""

import streamlit as st
import pandas as pd
import json
import yaml
import tempfile
import os
from pathlib import Path
from io import StringIO
import matplotlib.pyplot as plt
import matplotlib
import numpy as np

# 日本語フォント設定
matplotlib.rcParams['font.family'] = ['Hiragino Sans', 'Hiragino Kaku Gothic ProN', 'Yu Gothic', 'Meiryo', 'Takao', 'IPAexGothic', 'IPAPGothic', 'VL PGothic', 'Noto Sans CJK JP', 'sans-serif']
matplotlib.rcParams['axes.unicode_minus'] = False

# Add src to path
import sys
sys.path.insert(0, str(Path(__file__).parent))

from src.io.loader import DataLoader
from src.io.exporter import ResultExporter
from src.io.demand_generator import (
    generate_demand_from_flights,
    generate_demand_csv_content,
    summarize_flights_by_slot,
    calculate_total_demand,
)
from src.simulation.engine import SimulationEngine, SimulationConfig
from src.simulation.arrival import DemandSlot
from src.analysis.statistics import StatisticsCalculator
from src.analysis.heatmap import HeatmapGenerator
from src.analysis.animation import AnimationGenerator

# OCR import (optional - may not be installed)
try:
    from src.io.ocr import extract_times_from_image, extract_times_from_multiple_images
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

# Image coordinates import (optional - for layout editor)
try:
    from streamlit_image_coordinates import streamlit_image_coordinates
    IMAGE_COORDINATES_AVAILABLE = True
except ImportError:
    IMAGE_COORDINATES_AVAILABLE = False


# Page config
st.set_page_config(
    page_title="空港混雑シミュレーター",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1e3a5f;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.2rem;
        color: #5a7a9a;
        margin-bottom: 2rem;
    }
    .stat-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
        text-align: center;
    }
    .stat-value {
        font-size: 2rem;
        font-weight: 700;
    }
    .stat-label {
        font-size: 0.9rem;
        opacity: 0.9;
    }
    .section-header {
        font-size: 1.3rem;
        font-weight: 600;
        color: #2c3e50;
        margin-top: 2rem;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #3498db;
    }
</style>
""", unsafe_allow_html=True)


def check_password():
    """Basic認証を行う。認証成功でTrueを返す。"""
    
    def password_entered():
        """パスワードが正しいかチェック"""
        if (st.session_state["username"] == "admin" and 
            st.session_state["password"] == "airportDX"):
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # パスワードをセッションから削除
            del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    # ログインフォーム表示
    st.markdown("## 🔐 ログイン")
    st.text_input("ユーザー名", key="username")
    st.text_input("パスワード", type="password", key="password")
    st.button("ログイン", on_click=password_entered)
    
    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("ユーザー名またはパスワードが正しくありません")
    
    return False


def format_wait_time(seconds: float) -> str:
    """Format wait time in both seconds and minutes if over 60 seconds."""
    if seconds < 60:
        return f"{seconds:.1f}秒"
    else:
        minutes = seconds / 60
        return f"{seconds:.0f}秒 ({minutes:.1f}分)"


def init_session_state():
    """Initialize session state variables."""
    if 'simulation_result' not in st.session_state:
        st.session_state.simulation_result = None
    if 'layout_image_path' not in st.session_state:
        st.session_state.layout_image_path = None
    if 'nodes' not in st.session_state:
        st.session_state.nodes = get_default_nodes()
    if 'areas' not in st.session_state:
        st.session_state.areas = get_default_areas()


def get_default_nodes():
    """Get default node coordinates."""
    return {
        "source": {"x": 120, "y": 800, "note": "旅客生成点"},
        "checkin_kiosk": {"x": 300, "y": 650, "note": "チェックインキオスク"},
        "checkin_counter": {"x": 520, "y": 640, "note": "チェックインカウンター"},
        "baggage_counter": {"x": 650, "y": 520, "note": "手荷物カウンター"},
        "tag_kiosk": {"x": 340, "y": 520, "note": "タグ発券機"},
        "drop_point": {"x": 520, "y": 500, "note": "ドロップポイント"},
        "security_gate": {"x": 700, "y": 250, "note": "保安検査入口"},
    }


def get_default_areas():
    """Get default area polygons."""
    return {
        "checkin_zone": {"polygon": [[200,700],[600,700],[600,580],[200,580]], "note": "チェックイン前滞留"},
        "baggage_counter_zone": {"polygon": [[600,560],[750,560],[750,460],[600,460]], "note": "手荷物カウンター前滞留"},
        "tag_zone": {"polygon": [[250,560],[450,560],[450,460],[250,460]], "note": "タグ発券前滞留"},
        "drop_zone": {"polygon": [[450,560],[600,560],[600,430],[450,430]], "note": "ドロップ前滞留"},
        "security_front": {"polygon": [[620,320],[760,320],[760,220],[620,220]], "note": "保安入口前滞留"},
    }


def get_default_demand():
    """Get default demand data."""
    times = []
    for hour in range(6, 22):
        for minute in [0, 30]:
            start = f"{hour:02d}:{minute:02d}"
            if minute == 0:
                end = f"{hour:02d}:30"
            else:
                end = f"{hour+1:02d}:00"
            times.append({"time_slot_start": start, "time_slot_end": end, "pax_count": 0})
    return pd.DataFrame(times)


def sidebar_config():
    """Render sidebar configuration."""
    st.sidebar.markdown("## ⚙️ シミュレーション設定")
    
    # Arrival distribution
    st.sidebar.markdown("### 📊 到着分布")
    arrival_df = st.sidebar.slider("自由度 (df)", 1, 30, 7, help="t分布の自由度")
    arrival_mean = st.sidebar.slider("平均到着時間 (分前)", 20, 120, 70, help="出発前の平均到着時間")
    arrival_scale = st.sidebar.slider("スケール", 5, 50, 20, help="分布のスケールパラメータ")
    
    # Branching probabilities
    st.sidebar.markdown("### 🔀 分岐率")
    p_online = st.sidebar.slider("オンライン率", 0.0, 1.0, 0.40, 0.05)
    p_kiosk = st.sidebar.slider("キオスク率", 0.0, 1.0, 0.40, 0.05)
    p_counter = 1.0 - p_online - p_kiosk
    st.sidebar.text(f"チェックインカウンター率: {p_counter:.2f}")
    p_baggage = st.sidebar.slider("預け手荷物率", 0.0, 1.0, 0.50, 0.05)
    p_baggage_counter = st.sidebar.slider("手荷物カウンター率", 0.0, 1.0, 0.10, 0.05, 
                                          help="預け荷物ありの人が手荷物カウンターを使う率（残りはセルフ）")
    
    # Capacities
    st.sidebar.markdown("### 🏗️ 設備台数")
    cap_kiosk = st.sidebar.number_input("チェックインキオスク", 1, 50, 8)
    cap_counter = st.sidebar.number_input("チェックインカウンター", 1, 20, 2, help="チェックインのみ")
    cap_baggage_counter = st.sidebar.number_input("手荷物カウンター", 1, 20, 6, help="タグ発券＋預け入れ一括")
    cap_tag = st.sidebar.number_input("タグ発券機", 1, 50, 10, help="セルフ預け入れ用")
    cap_drop = st.sidebar.number_input("ドロップポイント", 1, 20, 2, help="セルフ預け入れ用")
    
    # Service times
    st.sidebar.markdown("### ⏱️ 処理時間 (秒)")
    service_kiosk = st.sidebar.number_input("キオスク処理時間", 10, 300, 70)
    service_counter = st.sidebar.number_input("カウンター処理時間", 30, 600, 150, help="チェックインのみ")
    service_baggage_counter = st.sidebar.number_input("手荷物カウンター処理時間", 30, 600, 180, help="タグ発券＋預け入れ一括")
    service_tag = st.sidebar.number_input("タグ発券時間", 10, 200, 70)
    service_drop = st.sidebar.number_input("ドロップ時間", 1, 300, 70)
    
    # Group settings
    st.sidebar.markdown("### 👥 グループ設定")
    p_single = st.sidebar.slider("単独旅客率", 0.0, 1.0, 0.70, 0.05)
    
    return SimulationConfig(
        arrival_df=arrival_df,
        arrival_mean_min_before=arrival_mean,
        arrival_scale=arrival_scale,
        p_online=p_online,
        p_kiosk=p_kiosk,
        p_counter=max(0, p_counter),
        p_baggage=p_baggage,
        p_baggage_counter=p_baggage_counter,
        p_single=p_single,
        capacity_checkin_kiosk=cap_kiosk,
        capacity_checkin_counter=cap_counter,
        capacity_baggage_counter=cap_baggage_counter,
        capacity_tag_kiosk=cap_tag,
        capacity_drop_point=cap_drop,
        service_checkin_kiosk_mean=service_kiosk,
        service_checkin_counter_mean=service_counter,
        service_baggage_counter_mean=service_baggage_counter,
        service_tag_kiosk_mean=service_tag,
        service_drop_point_mean=service_drop,
    )


def render_file_upload():
    """Render file upload section."""
    st.markdown('<div class="section-header">📁 ファイルアップロード</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("#### 需要データ (CSV)")
        demand_file = st.file_uploader(
            "demand.csv",
            type=['csv'],
            key='demand_upload',
            help="time_slot_start, time_slot_end, pax_count 列を含むCSV"
        )
        
        if demand_file:
            try:
                content = demand_file.read().decode('utf-8')
                st.session_state.demand_slots = DataLoader.load_demand_from_string(content)
                st.success(f"✅ {len(st.session_state.demand_slots)} スロット読み込み")
            except Exception as e:
                st.error(f"❌ 読み込みエラー: {e}")
    
    with col2:
        st.markdown("#### レイアウト画像 (PNG)")
        layout_image = st.file_uploader(
            "layout.png",
            type=['png', 'jpg', 'jpeg'],
            key='layout_upload',
            help="背景画像としてヒートマップに重畳"
        )
        
        if layout_image:
            # Save to temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as f:
                f.write(layout_image.read())
                st.session_state.layout_image_path = f.name
            st.success("✅ レイアウト画像読み込み完了")
            st.image(layout_image, width=200)
    
    with col3:
        st.markdown("#### レイアウト設定 (JSON)")
        layout_json = st.file_uploader(
            "layout.json",
            type=['json'],
            key='layout_json_upload',
            help="ノード座標とエリアポリゴンを定義"
        )
        
        if layout_json:
            try:
                content = json.load(layout_json)
                nodes, areas, _ = DataLoader.load_layout_from_dict(content)
                st.session_state.nodes = nodes
                st.session_state.areas = areas
                st.success(f"✅ {len(nodes)} ノード, {len(areas)} エリア")
            except Exception as e:
                st.error(f"❌ 読み込みエラー: {e}")


def render_timetable_ocr():
    """Render timetable OCR section for generating demand from flight schedules."""
    st.markdown('<div class="section-header">📷 時刻表から需要データを生成</div>', unsafe_allow_html=True)
    
    if not OCR_AVAILABLE:
        st.warning(
            "⚠️ OCR機能を使用するには追加のインストールが必要です:\n"
            "```\n"
            "pip install pytesseract\n"
            "brew install tesseract tesseract-lang  # macOS\n"
            "```"
        )
        return
    
    # Initialize session state for flights
    if 'extracted_flights' not in st.session_state:
        st.session_state.extracted_flights = []
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("#### 時刻表画像をアップロード")
        uploaded_files = st.file_uploader(
            "時刻表PNG/JPG (複数可)",
            type=['png', 'jpg', 'jpeg'],
            accept_multiple_files=True,
            key='timetable_upload',
            help="航空便の時刻表画像をアップロードしてください。複数ファイル可。"
        )
        
        if uploaded_files:
            if st.button("🔍 OCRで時刻を抽出", type="primary"):
                with st.spinner("OCR処理中..."):
                    all_times = []
                    for uploaded_file in uploaded_files:
                        try:
                            # getvalue()を使用してファイル全体のバイトを取得（read()と異なりシーク位置に依存しない）
                            image_bytes = uploaded_file.getvalue()
                            if not image_bytes:
                                st.warning(f"⚠️ {uploaded_file.name}: ファイルが空です")
                                continue
                            times = extract_times_from_image(image_bytes)
                            all_times.extend(times)
                            st.success(f"✅ {uploaded_file.name}: {len(times)} 件の時刻を抽出")
                        except Exception as e:
                            st.error(f"❌ {uploaded_file.name}: {e}")
                    
                    # Deduplicate and sort
                    unique_times = sorted(set(all_times), 
                                         key=lambda t: (int(t.split(':')[0]), int(t.split(':')[1])))
                    st.session_state.extracted_flights = [
                        {"departure_time": t, "include": True} for t in unique_times
                    ]
                    st.success(f"✅ 合計 {len(unique_times)} 便を抽出しました")
    
    with col2:
        st.markdown("#### 設定")
        pax_per_flight = st.number_input(
            "1便あたり乗客数",
            min_value=10,
            max_value=500,
            value=150,
            step=10,
            key='pax_per_flight',
            help="全便共通の乗客数"
        )
    
    # Show extracted flights
    if st.session_state.extracted_flights:
        st.markdown("#### ✈️ 抽出された便一覧 (編集可能)")
        
        # Create editable dataframe
        flights_df = pd.DataFrame(st.session_state.extracted_flights)
        
        edited_flights = st.data_editor(
            flights_df,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "departure_time": st.column_config.TextColumn(
                    "出発時刻",
                    help="HH:MM形式",
                    width="medium",
                ),
                "include": st.column_config.CheckboxColumn(
                    "含める",
                    help="需要計算に含める",
                    default=True,
                ),
            },
        )
        
        # Update session state
        st.session_state.extracted_flights = edited_flights.to_dict('records')
        
        # Filter included flights
        included_times = [
            f['departure_time'] for f in st.session_state.extracted_flights 
            if f.get('include', True)
        ]
        
        # Show summary
        total_flights, total_pax = calculate_total_demand(included_times, pax_per_flight)
        
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            st.metric("総便数", f"{total_flights} 便")
        with col_b:
            st.metric("総旅客数", f"{total_pax} 人")
        with col_c:
            st.metric("1便あたり", f"{pax_per_flight} 人")
        
        # Generate demand button
        if st.button("📊 需要データを生成", type="primary"):
            # Generate demand slots
            demand_slots = generate_demand_from_flights(
                departure_times=included_times,
                pax_per_flight=pax_per_flight,
            )
            
            # Update demand dataframe
            demand_data = []
            for slot in demand_slots:
                start_hour = slot.start_minutes // 60
                start_min = slot.start_minutes % 60
                end_hour = slot.end_minutes // 60
                end_min = slot.end_minutes % 60
                demand_data.append({
                    "time_slot_start": f"{start_hour:02d}:{start_min:02d}",
                    "time_slot_end": f"{end_hour:02d}:{end_min:02d}",
                    "pax_count": slot.pax_count,
                })
            
            st.session_state.demand_df = pd.DataFrame(demand_data)
            st.session_state.demand_slots = demand_slots
            
            st.success(f"✅ 需要データを生成しました！（総旅客数: {total_pax} 人）")
            st.rerun()


def render_demand_editor():
    """Render demand data editor."""
    st.markdown('<div class="section-header">📋 需要データ編集</div>', unsafe_allow_html=True)
    
    if 'demand_df' not in st.session_state:
        st.session_state.demand_df = get_default_demand()
    
    edited_df = st.data_editor(
        st.session_state.demand_df,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "time_slot_start": st.column_config.TextColumn("開始時刻", help="HH:MM形式"),
            "time_slot_end": st.column_config.TextColumn("終了時刻", help="HH:MM形式"),
            "pax_count": st.column_config.NumberColumn("旅客数", min_value=0, max_value=10000, step=10),
        },
    )
    
    st.session_state.demand_df = edited_df
    
    # Convert to demand slots
    slots = []
    for _, row in edited_df.iterrows():
        try:
            from src.simulation.arrival import parse_time_to_minutes
            start_min = parse_time_to_minutes(row['time_slot_start'])
            end_min = parse_time_to_minutes(row['time_slot_end'])
            slots.append(DemandSlot(
                start_minutes=start_min,
                end_minutes=end_min,
                pax_count=int(row['pax_count']),
            ))
        except:
            pass
    
    st.session_state.demand_slots = slots
    
    total_pax = sum(s.pax_count for s in slots)
    st.info(f"📊 総旅客数: **{total_pax}** 人 ({len(slots)} 時間帯)")


def run_simulation(config: SimulationConfig):
    """Run simulation with progress."""
    if 'demand_slots' not in st.session_state or not st.session_state.demand_slots:
        st.error("需要データがありません。需要データを入力してください。")
        return
    
    with st.spinner("シミュレーション実行中..."):
        # Initialize engine
        engine = SimulationEngine(
            config=config,
            nodes=st.session_state.nodes,
            areas=st.session_state.areas,
        )
        
        # Run simulation
        result = engine.run(st.session_state.demand_slots)
        st.session_state.simulation_result = result
    
    st.success("✅ シミュレーション完了!")


def render_results():
    """Render simulation results."""
    result = st.session_state.simulation_result
    
    if result is None:
        st.info("シミュレーションを実行してください")
        return
    
    # Calculate statistics
    stats_calc = StatisticsCalculator(result)
    process_stats = stats_calc.calculate_process_stats()
    overall_stats = stats_calc.calculate_overall_stats()
    
    # Summary cards
    st.markdown('<div class="section-header">📈 結果サマリー</div>', unsafe_allow_html=True)
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("総グループ数", overall_stats.total_groups)
    with col2:
        st.metric("総旅客数", overall_stats.total_passengers)
    with col3:
        st.metric("平均所要時間", f"{overall_stats.mean_total_time/60:.1f} 分")
    with col4:
        st.metric("95%所要時間", f"{overall_stats.p95_total_time/60:.1f} 分")
    
    # Process statistics
    st.markdown('<div class="section-header">⏱️ 工程別待ち時間</div>', unsafe_allow_html=True)
    
    if process_stats:
        stats_data = []
        for name, stats in process_stats.items():
            stats_data.append({
                "工程": name,
                "件数（組）": stats.count,
                "平均": format_wait_time(stats.mean_wait),
                "中央値": format_wait_time(stats.p50_wait),
                "95%": format_wait_time(stats.p95_wait),
                "最大": format_wait_time(stats.max_wait),
            })
        st.dataframe(pd.DataFrame(stats_data), use_container_width=True)
        st.caption("※ 件数はグループ単位（4人グループでも1組としてカウント）")
    else:
        st.info("待ち時間データがありません")
    
    # Time-based wait time analysis (10-minute intervals)
    st.markdown('<div class="section-header">📊 時間帯別待ち時間（10分刻み）</div>', unsafe_allow_html=True)
    render_wait_time_by_interval(result)
    
    # Visualizations
    st.markdown('<div class="section-header">📊 可視化</div>', unsafe_allow_html=True)
    
    tab1, tab2, tab3 = st.tabs(["キュー長推移", "ヒートマップ", "アニメーション"])
    
    with tab1:
        render_queue_charts(result)
    
    with tab2:
        render_heatmap(result)
    
    with tab3:
        render_animation(result)


def render_wait_time_by_interval(result, interval_minutes: int = 10):
    """Render wait time statistics by time interval."""
    from src.models.passenger import CheckinType, BaggageDropType
    
    if not result.completed_groups:
        st.info("データがありません")
        return
    
    # Determine time range
    all_times = []
    for g in result.completed_groups:
        if g.checkin_queue_enter is not None:
            all_times.append(g.checkin_queue_enter)
        if g.baggage_counter_queue_enter is not None:
            all_times.append(g.baggage_counter_queue_enter)
        if g.tag_queue_enter is not None:
            all_times.append(g.tag_queue_enter)
        if g.drop_queue_enter is not None:
            all_times.append(g.drop_queue_enter)
    
    if not all_times:
        st.info("待ち時間データがありません")
        return
    
    min_time = min(all_times)
    max_time = max(all_times)
    
    # Create time slots
    interval_sec = interval_minutes * 60
    start_slot = int(min_time // interval_sec) * interval_sec
    end_slot = int(max_time // interval_sec + 1) * interval_sec
    
    slots = list(range(start_slot, end_slot + interval_sec, interval_sec))
    
    # Process names and their wait time getters
    processes = [
        ("checkin_kiosk", "チェックインキオスク", 
         lambda g: (g.checkin_queue_enter, g.checkin_wait_time) if g.checkin_type == CheckinType.KIOSK else (None, None)),
        ("checkin_counter", "チェックインカウンター",
         lambda g: (g.checkin_queue_enter, g.checkin_wait_time) if g.checkin_type == CheckinType.COUNTER else (None, None)),
        ("baggage_counter", "手荷物カウンター",
         lambda g: (g.baggage_counter_queue_enter, g.baggage_counter_wait_time)),
        ("tag_kiosk", "タグ発券機",
         lambda g: (g.tag_queue_enter, g.tag_wait_time)),
        ("drop_point", "ドロップポイント",
         lambda g: (g.drop_queue_enter, g.drop_wait_time)),
    ]
    
    # Calculate stats for each slot and process
    data_rows = []
    
    for i in range(len(slots) - 1):
        slot_start = slots[i]
        slot_end = slots[i + 1]
        
        # Convert to readable time
        start_min = slot_start // 60
        start_h = int(start_min // 60)
        start_m = int(start_min % 60)
        time_label = f"{start_h:02d}:{start_m:02d}"
        
        row = {"時間帯": time_label}
        
        for proc_key, proc_name, wait_getter in processes:
            wait_times = []
            for g in result.completed_groups:
                queue_enter, wait_time = wait_getter(g)
                if queue_enter is not None and wait_time is not None:
                    if slot_start <= queue_enter < slot_end:
                        wait_times.append(wait_time)
            
            if wait_times:
                avg_wait = np.mean(wait_times)
                max_wait = np.max(wait_times)
                count = len(wait_times)
                row[f"{proc_name}_件数"] = count
                row[f"{proc_name}_平均"] = format_wait_time(avg_wait)
                row[f"{proc_name}_最大"] = format_wait_time(max_wait)
                row[f"{proc_name}_平均_raw"] = avg_wait  # For chart
            else:
                row[f"{proc_name}_件数"] = 0
                row[f"{proc_name}_平均"] = "-"
                row[f"{proc_name}_最大"] = "-"
                row[f"{proc_name}_平均_raw"] = 0
        
        data_rows.append(row)
    
    # Filter out empty rows
    data_rows = [row for row in data_rows if any(
        row.get(f"{proc_name}_件数", 0) > 0 for _, proc_name, _ in processes
    )]
    
    if not data_rows:
        st.info("待ち時間データがありません")
        return
    
    df = pd.DataFrame(data_rows)
    
    # Create tabs for each process
    process_tabs = st.tabs([proc_name for _, proc_name, _ in processes])
    
    for tab, (proc_key, proc_name, _) in zip(process_tabs, processes):
        with tab:
            cols = ["時間帯", f"{proc_name}_件数", f"{proc_name}_平均", f"{proc_name}_最大"]
            raw_col = f"{proc_name}_平均_raw"
            available_cols = [c for c in cols if c in df.columns]
            if available_cols:
                display_df = df[available_cols + [raw_col]].copy()
                display_df.columns = ["時間帯", "件数（組）", "平均待ち", "最大待ち", "_raw"]
                
                # Filter rows with data
                display_df = display_df[display_df["件数（組）"] > 0]
                
                if not display_df.empty:
                    # Display table without raw column
                    st.dataframe(display_df[["時間帯", "件数（組）", "平均待ち", "最大待ち"]], 
                                use_container_width=True, hide_index=True)
                    st.caption("※ 件数はグループ単位（4人グループでも1組としてカウント）")
                    
                    # Create chart using raw values
                    chart_data = display_df[display_df["_raw"] > 0][["時間帯", "_raw"]].copy()
                    chart_data.columns = ["時間帯", "平均待ち時間(秒)"]
                    
                    if not chart_data.empty:
                        st.bar_chart(chart_data.set_index("時間帯"))
                else:
                    st.info(f"{proc_name}のデータはありません")


def render_queue_charts(result):
    """Render queue length charts."""
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    axes = axes.flatten()
    
    resources = ['checkin_kiosk', 'checkin_counter', 'baggage_counter', 'tag_kiosk', 'drop_point']
    titles = ['チェックインキオスク', 'チェックインカウンター', '手荷物カウンター', 'タグ発券機', 'ドロップポイント']
    
    for i, (resource, title) in enumerate(zip(resources, titles)):
        ax = axes[i]
        history = result.queue_histories.get(resource, [])
        
        if history:
            times = [s.time / 60 for s in history]
            queue_pax = [s.queue_pax_count for s in history]
            
            ax.fill_between(times, queue_pax, alpha=0.3, color='steelblue')
            ax.plot(times, queue_pax, linewidth=1, color='steelblue')
            ax.set_xlabel('時間 (分)')
            ax.set_ylabel('待ち人数')
            ax.set_title(title)
            ax.grid(True, alpha=0.3)
        else:
            ax.text(0.5, 0.5, 'データなし', ha='center', va='center', transform=ax.transAxes)
            ax.set_title(title)
    
    # Hide the unused 6th subplot
    if len(resources) < len(axes):
        axes[-1].axis('off')
    
    plt.suptitle('工程別待ち人数の推移', fontsize=14, fontweight='bold')
    plt.tight_layout()
    st.pyplot(fig)
    plt.close()


def render_heatmap(result):
    """Render heatmap."""
    heatmap_gen = HeatmapGenerator(
        layout_image_path=st.session_state.layout_image_path,
        image_size=(800, 1000),
    )
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as f:
        heatmap_path = f.name
    
    heatmap_gen.generate_occupancy_heatmap(
        result=result,
        nodes=st.session_state.nodes,
        areas=st.session_state.areas,
        output_path=heatmap_path,
        title="滞留人数ヒートマップ",
    )
    
    st.image(heatmap_path, use_column_width=True)
    
    # Download button
    with open(heatmap_path, 'rb') as f:
        st.download_button(
            label="📥 ヒートマップをダウンロード",
            data=f.read(),
            file_name="heatmap.png",
            mime="image/png",
        )


def render_animation(result):
    """Render animation generation."""
    if not result.position_snapshots:
        st.warning("位置データがありません")
        return
    
    st.info(f"📍 {len(result.position_snapshots)} フレームのデータがあります")
    
    if st.button("🎬 アニメーション生成", type="primary"):
        with st.spinner("アニメーション生成中 (時間がかかる場合があります)..."):
            anim_gen = AnimationGenerator(
                layout_image_path=st.session_state.layout_image_path,
                fps=10,
            )
            
            with tempfile.NamedTemporaryFile(delete=False, suffix='.gif') as f:
                anim_path = f.name
            
            anim_gen.generate_animation(
                result=result,
                nodes=st.session_state.nodes,
                areas=st.session_state.areas,
                output_path=anim_path,
                format="gif",
                max_frames=300,
            )
            
            st.session_state.animation_path = anim_path
        
        st.success("✅ アニメーション生成完了!")
    
    if 'animation_path' in st.session_state and st.session_state.animation_path:
        st.image(st.session_state.animation_path)
        
        with open(st.session_state.animation_path, 'rb') as f:
            st.download_button(
                label="📥 アニメーションをダウンロード",
                data=f.read(),
                file_name="animation.gif",
                mime="image/gif",
            )


def render_export():
    """Render export section."""
    result = st.session_state.simulation_result
    
    if result is None:
        return
    
    st.markdown('<div class="section-header">💾 結果エクスポート</div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Stats CSV
        stats_calc = StatisticsCalculator(result)
        process_stats = stats_calc.calculate_process_stats()
        
        stats_data = []
        for name, stats in process_stats.items():
            stats_data.append({
                "process": name,
                "count": stats.count,
                "mean_wait_sec": stats.mean_wait,
                "p95_wait_sec": stats.p95_wait,
                "max_wait_sec": stats.max_wait,
            })
        
        if stats_data:
            csv = pd.DataFrame(stats_data).to_csv(index=False)
            st.download_button(
                label="📊 統計CSVダウンロード",
                data=csv,
                file_name="stats_summary.csv",
                mime="text/csv",
            )
    
    with col2:
        # Passenger details
        details = []
        for group in result.completed_groups:
            details.append({
                "group_id": group.group_id,
                "group_size": group.group_size,
                "checkin_type": group.checkin_type.value,
                "has_baggage": group.has_baggage,
                "checkin_wait": group.checkin_wait_time,
                "tag_wait": group.tag_wait_time,
                "drop_wait": group.drop_wait_time,
                "total_time": group.total_process_time,
            })
        
        if details:
            csv = pd.DataFrame(details).to_csv(index=False)
            st.download_button(
                label="👥 旅客詳細CSVダウンロード",
                data=csv,
                file_name="passenger_details.csv",
                mime="text/csv",
            )
    
    with col3:
        # Queue history
        queue_data = []
        for resource_name, history in result.queue_histories.items():
            for snapshot in history:
                queue_data.append({
                    "time_sec": snapshot.time,
                    "resource": resource_name,
                    "queue_groups": snapshot.queue_length,
                    "queue_pax": snapshot.queue_pax_count,
                })
        
        if queue_data:
            csv = pd.DataFrame(queue_data).to_csv(index=False)
            st.download_button(
                label="📈 キュー長CSVダウンロード",
                data=csv,
                file_name="queue_length.csv",
                mime="text/csv",
            )


def render_layout_editor():
    """Render layout editor section for defining node coordinates on the image."""
    st.markdown('<div class="section-header">🗺️ レイアウト編集</div>', unsafe_allow_html=True)
    
    if not IMAGE_COORDINATES_AVAILABLE:
        st.warning(
            "⚠️ レイアウト編集機能を使用するには追加のインストールが必要です:\n"
            "```\n"
            "pip install streamlit-image-coordinates\n"
            "```"
        )
        return
    
    # Check if layout image is uploaded
    if st.session_state.layout_image_path is None:
        st.info("📷 まず「設定 & 実行」タブでレイアウト画像（PNG）をアップロードしてください。")
        return
    
    st.markdown("""
    ### 使い方
    1. 下の画像上でクリックして座標を取得
    2. ノード名を選択して「座標を設定」ボタンをクリック
    3. エリアは4点をクリックして定義
    """)
    
    # Initialize editing state
    if 'editing_mode' not in st.session_state:
        st.session_state.editing_mode = 'node'  # 'node' or 'area'
    if 'area_points' not in st.session_state:
        st.session_state.area_points = []
    if 'last_click' not in st.session_state:
        st.session_state.last_click = None
    
    # Mode selection
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📍 ノード編集モード", type="primary" if st.session_state.editing_mode == 'node' else "secondary"):
            st.session_state.editing_mode = 'node'
            st.session_state.area_points = []
    with col2:
        if st.button("🔲 エリア編集モード", type="primary" if st.session_state.editing_mode == 'area' else "secondary"):
            st.session_state.editing_mode = 'area'
    
    # Load and display image with click detection
    from PIL import Image, ImageDraw, ImageFont
    
    img = Image.open(st.session_state.layout_image_path)
    
    # Draw existing nodes and areas on image
    draw = ImageDraw.Draw(img)
    
    # Draw areas (polygons)
    for area_name, area_data in st.session_state.areas.items():
        polygon = area_data.get('polygon', [])
        if len(polygon) >= 3:
            # Draw filled polygon with transparency
            flat_polygon = [tuple(p) for p in polygon]
            draw.polygon(flat_polygon, outline='blue', width=2)
            # Draw area name
            if polygon:
                center_x = sum(p[0] for p in polygon) // len(polygon)
                center_y = sum(p[1] for p in polygon) // len(polygon)
                draw.text((center_x, center_y), area_name, fill='blue')
    
    # Draw nodes
    for node_name, node_data in st.session_state.nodes.items():
        x, y = node_data.get('x', 0), node_data.get('y', 0)
        # Draw circle
        radius = 8
        draw.ellipse([x-radius, y-radius, x+radius, y+radius], fill='red', outline='darkred')
        # Draw label
        draw.text((x+10, y-5), node_name, fill='red')
    
    # Draw area points being defined
    if st.session_state.area_points:
        for i, point in enumerate(st.session_state.area_points):
            draw.ellipse([point[0]-5, point[1]-5, point[0]+5, point[1]+5], fill='green', outline='darkgreen')
            draw.text((point[0]+8, point[1]-5), str(i+1), fill='green')
        # Draw lines between points
        if len(st.session_state.area_points) >= 2:
            for i in range(len(st.session_state.area_points) - 1):
                draw.line([tuple(st.session_state.area_points[i]), tuple(st.session_state.area_points[i+1])], fill='green', width=2)
    
    # Display clickable image
    st.markdown("#### 📷 レイアウト画像（クリックで座標取得）")
    
    coords = streamlit_image_coordinates(img, key="layout_editor")
    
    if coords:
        click_x, click_y = coords['x'], coords['y']
        st.session_state.last_click = (click_x, click_y)
        
        if st.session_state.editing_mode == 'area':
            # Add point for area definition
            if len(st.session_state.area_points) < 4:
                # Check if this is a new click (not the same as last point)
                if not st.session_state.area_points or st.session_state.area_points[-1] != [click_x, click_y]:
                    st.session_state.area_points.append([click_x, click_y])
                    st.rerun()
    
    # Show current click coordinates
    if st.session_state.last_click:
        st.info(f"📍 最後にクリックした座標: X={st.session_state.last_click[0]}, Y={st.session_state.last_click[1]}")
    
    st.markdown("---")
    
    # Node editing UI
    if st.session_state.editing_mode == 'node':
        st.markdown("#### 📍 ノード座標設定")
        
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            node_names = list(st.session_state.nodes.keys())
            selected_node = st.selectbox("ノードを選択", node_names, key="selected_node")
        
        with col2:
            if st.session_state.last_click:
                new_x = st.number_input("X座標", value=st.session_state.last_click[0], key="node_x")
            else:
                current_x = st.session_state.nodes[selected_node].get('x', 0)
                new_x = st.number_input("X座標", value=current_x, key="node_x")
        
        with col3:
            if st.session_state.last_click:
                new_y = st.number_input("Y座標", value=st.session_state.last_click[1], key="node_y")
            else:
                current_y = st.session_state.nodes[selected_node].get('y', 0)
                new_y = st.number_input("Y座標", value=current_y, key="node_y")
        
        if st.button("✅ 座標を設定", key="set_node_coords"):
            st.session_state.nodes[selected_node]['x'] = new_x
            st.session_state.nodes[selected_node]['y'] = new_y
            st.success(f"✅ {selected_node} の座標を ({new_x}, {new_y}) に設定しました")
            st.rerun()
        
        # Show current nodes
        st.markdown("#### 現在のノード設定")
        nodes_df = pd.DataFrame([
            {"ノード名": name, "X": data.get('x', 0), "Y": data.get('y', 0), "説明": data.get('note', '')}
            for name, data in st.session_state.nodes.items()
        ])
        st.dataframe(nodes_df, use_container_width=True)
    
    # Area editing UI
    else:
        st.markdown("#### 🔲 エリア定義")
        
        st.write(f"クリックした点: {len(st.session_state.area_points)}/4")
        
        if st.session_state.area_points:
            for i, point in enumerate(st.session_state.area_points):
                st.write(f"  点{i+1}: ({point[0]}, {point[1]})")
        
        col1, col2 = st.columns(2)
        
        with col1:
            area_names = list(st.session_state.areas.keys())
            selected_area = st.selectbox("エリアを選択", area_names, key="selected_area")
        
        with col2:
            if st.button("🗑️ 点をクリア", key="clear_points"):
                st.session_state.area_points = []
                st.rerun()
        
        if len(st.session_state.area_points) == 4:
            if st.button("✅ エリアを設定", key="set_area_coords", type="primary"):
                st.session_state.areas[selected_area]['polygon'] = st.session_state.area_points.copy()
                st.success(f"✅ {selected_area} のポリゴンを設定しました")
                st.session_state.area_points = []
                st.rerun()
        
        # Show current areas
        st.markdown("#### 現在のエリア設定")
        areas_df = pd.DataFrame([
            {"エリア名": name, "ポリゴン点数": len(data.get('polygon', [])), "説明": data.get('note', '')}
            for name, data in st.session_state.areas.items()
        ])
        st.dataframe(areas_df, use_container_width=True)
    
    st.markdown("---")
    
    # Export layout JSON
    st.markdown("#### 💾 レイアウト設定をエクスポート")
    
    layout_data = {
        "px_per_meter": 10,
        "image_size": {"width": img.width, "height": img.height},
        "nodes": st.session_state.nodes,
        "areas": st.session_state.areas,
    }
    
    json_str = json.dumps(layout_data, ensure_ascii=False, indent=2)
    
    st.download_button(
        label="📥 layout.json をダウンロード",
        data=json_str,
        file_name="layout.json",
        mime="application/json",
    )


def main():
    """Main application."""
    if not check_password():
        st.stop()
    
    init_session_state()
    
    # Header
    st.markdown('<div class="main-header">✈️ 空港混雑シミュレーター</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-header">SimPy DESによる空港出発エリアの混雑シミュレーション</div>', unsafe_allow_html=True)
    
    # Sidebar config
    config = sidebar_config()
    
    # Main content tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🔧 設定 & 実行", "🗺️ レイアウト編集", "📷 時刻表OCR", "📊 結果", "📁 エクスポート"])
    
    with tab1:
        render_file_upload()
        st.markdown("---")
        render_demand_editor()
        st.markdown("---")
        
        col1, col2 = st.columns([3, 1])
        with col2:
            if st.button("🚀 シミュレーション実行", type="primary", use_container_width=True):
                run_simulation(config)
    
    with tab2:
        render_layout_editor()
    
    with tab3:
        render_timetable_ocr()
    
    with tab4:
        render_results()
    
    with tab5:
        render_export()


if __name__ == "__main__":
    main()

