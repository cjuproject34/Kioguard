# Qwen3.5 2B FP16·Q4·Q8 비교 v0.2

기준일: 2026-10-02
범위: revision `15852e8c16360a2fea060d615a32b45270f8a8fc`, prompt v3.1, 개발 gate 20건

## 보존된 집계 결과

| 지표 | FP16 | Q4_K_M | Q8_0 |
|---|---:|---:|---:|
| 모델 파일 | 3.897 GB | 1.312 GB | 2.077 GB |
| Macro intent F1 | 0.4741 | 0.4694 | 0.4622 |
| 계약 유효율 | 90% | 90% | 90% |
| 완전 의미 일치율 | 15% | 15% | 15% |
| fallback 일치율 | 80% | 85% | 85% |
| 고영향 완전 일치율 | 0% | 0% | 0% |
| 위험 추가 행동 | 2건 | 1건 | 2건 |
| must-not 위반 | 1건 | 0건 | 1건 |
| 평균 생성 시간 | 비교 제외 | 71.85초 | 105.17초 |

Q4_K_M은 Q8_0보다 파일이 36.8% 작고 같은 CPU 실행에서 평균 생성 시간이 31.7% 짧다. 집계 Macro F1도 0.0071 높다. 현재 결과에서는 후속 검증 후보로 Q4_K_M이 우선이다. 세 형식 모두 고영향 완전 일치율이 0%이므로 배포 승인이나 QAT 시작 근거로 사용하지 않는다.

## 남아 있던 검증 공백

FP16 사례별 출력과 점수는 저장돼 있지만 Q4_K_M·Q8_0의 사례별 원출력과 정규화 출력은 Colab 런타임에만 생성되고 Git과 Drive에 보존되지 않았다. 이 때문에 집계 차이를 `FP16 공통 오류`, `Q4만 발생`, `Q8만 발생`, `transport/parser 오류`로 귀속할 수 없었다.

FP16은 Transformers/PyTorch/Tesla T4, PTQ는 llama.cpp CPU `-ngl 0`에서 실행돼 기존 시간은 서로 비교하지 않는다. FP16 평균 시간도 PTQ 집계의 3.1초와 저장된 run manifest의 6.20초가 일치하지 않는다.

## 재실행 방법

`evaluation/scripts/run_qwen35_2b_gguf_case_replay.py`는 동일한 llama.cpp commit과 CPU 설정에서 F16 GGUF, Q4_K_M, Q8_0을 같은 20건에 실행한다. 각 사례가 끝날 때마다 Drive에 다음을 저장해 런타임 중단 후에도 이어서 실행할 수 있다.

- `predictions_raw.jsonl`
- `predictions_normalized.jsonl`
- `predictions.jsonl`
- `run_manifest.json`
- `scores/summary.json`, `scores/summary_v2.json`
- `diagnostics/error_summary.json`
- 전체 형식의 `case_level_comparison.csv`와 `aggregate_comparison.json`

기본 출력 위치는 `/content/drive/MyDrive/KioGuard/experiments/QWEN35_2B_GGUF_CASE_REPLAY_V1`이다. 최종 판정은 이 재실행의 사례별 결과를 기준으로 갱신한다.
