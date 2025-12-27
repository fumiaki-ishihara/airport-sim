# 空港出発エリア混雑シミュレーター

SimPy（離散イベントシミュレーション）を使用した、空港出発エリアの混雑シミュレーションシステムです。

## 機能

- **DESシミュレーション**: SimPyによる離散イベントシミュレーション
- **工程別分析**: チェックイン（オンライン/kiosk/カウンター）、タグ発券、ドロップポイント
- **統計出力**: 待ち時間（平均/95%/最大）、キュー長時系列
- **可視化**: 滞留ヒートマップ、MP4/GIFアニメーション
- **シナリオ比較**: 複数パラメータでの一括実行と比較

## インストール

```bash
cd /Users/fu.ishihara/projects/airport-sim
pip install -r requirements.txt
```

## 使用方法

### CLI実行

```bash
# 単一シナリオ実行
python run_simulation.py --scenario config/scenario_base.yaml --demand data/demand.csv

# パラメータスイープ実行
python run_simulation.py --sweep config/scenario_sweep.csv --demand data/demand.csv

# アニメーション出力付き
python run_simulation.py --scenario config/scenario_base.yaml --demand data/demand.csv --animation
```

### Webアプリ実行

```bash
streamlit run app.py
```

## 入力ファイル

### demand.csv
時間帯別の旅客数を定義します。

```csv
time_slot_start,time_slot_end,pax_count
06:00,06:30,50
06:30,07:00,100
...
```

### scenario.yaml
シミュレーションパラメータを定義します。

```yaml
arrival:
  df: 7                          # t分布の自由度
  mean_min_before_departure: 70  # 出発前平均到着時間（分）
  scale: 20                      # スケールパラメータ

branching:
  p_online: 0.3   # オンラインチェックイン率
  p_kiosk: 0.5    # kioskチェックイン率
  p_counter: 0.2  # カウンターチェックイン率
  p_baggage: 0.5  # 預け手荷物あり率

capacity:
  checkin_kiosk: 8
  checkin_counter: 6
  tag_kiosk: 4
  drop_point: 4

service_time:
  checkin_kiosk: {mean: 70, std: 15}
  checkin_counter: {mean: 180, std: 40}
  tag_kiosk: {mean: 45, std: 10}
  drop_point: {mean: 120, std: 30}
```

### layout.json
ノード座標とエリアポリゴンを定義します。

### layout.png
背景画像（Webアプリからアップロード可能）

## 出力ファイル

| ファイル | 内容 |
|---------|------|
| `stats_summary.csv` | 工程別待ち時間統計 |
| `queue_length.csv` | 時系列キュー長 |
| `area_occupancy.csv` | エリア別滞留人数 |
| `heatmap.png` | 滞留ヒートマップ |
| `animation.mp4` / `animation.gif` | アニメーション |
| `scenario_comparison.csv` | シナリオ比較結果 |

## 旅客動線

```
到着 → チェックイン（online/kiosk/counter）
         ↓
    預け手荷物判定
    ├── なし → 保安入口（終了）
    └── あり → タグ発券 → ドロップ → 保安入口（終了）
```

## ライセンス

MIT License


