# KioGuard 의도분류 평가 데이터·모델 비교

기준일: 2026-10-05
상태: **개발용 초안. 사람 검수 전이며 독립 test가 아님**

## 이번 자료의 목적

새 14개 의도와 안전한 fallback 기준으로 모델을 같은 조건에서 비교한다. 과거 8개 의도 점수는 이 결과에 합치지 않는다. 기존 48발화는 새 계약으로 다시 구성한 회귀 세트로만 사용한다.

평가 출력 계약 v3은 다음 두 항목만 최상위에 둔다.

```json
{
  "requests": [
    {
      "request_id": "r1",
      "intent": "NAVIGATE",
      "target": "APP_UI",
      "slots": {"destination": "HOME"},
      "condition": null,
      "depends_on": null
    }
  ],
  "fallback": null
}
```

- `requests`: 사용자 발화에 실제로 포함된 요청만 기록한다.
- `condition`: 조건부 요청의 검증할 상태를 구조화한다.
- `depends_on`: 복합 요청의 선행 관계를 기록한다.
- `fallback`: 대상·문맥·입력 복구 질문, 범위 밖, 실행하지 않아야 하는 응답을 기록한다.
- Markdown code fence 제거는 전송 정규화로 허용한다. 누락 괄호 보충, 라벨 별칭 치환, 의미 추정은 허용하지 않는다.

## 데이터 구성

| 파일 | 사례 수 | 용도 |
|---|---:|---|
| `data/selection_dev_v0.1.jsonl` | 84 | 14개 의도별 6개 핵심 개발 사례 |
| `data/selection_challenge_v0.1.jsonl` | 34 | 재질문·범위 밖·부정·조건·복합 요청·문맥 대조 |
| `data/legacy48_regression_v1.2.jsonl` | 48 | 기존 발화의 회귀 평가. 문맥은 새 계약용으로 구성 |
| `data/evaluation_review_v0.1.csv` | 166 | 사람 검수용 평면 표 |

`selection_*` 118건은 모델과 프롬프트를 고르는 개발 데이터다. 같은 자료를 보고 설정을 수정하므로 최종 일반화 점수로 사용할 수 없다. 최종 후보를 고른 뒤 별도 작성자·검수자가 만든 비공개 test가 필요하다.

## 문맥 원칙

모델에는 앱이 확인할 수 있는 상태만 제공한다.

- 현재 단계와 화면
- 주문·결제의 확인된 상태
- 선택된 항목과 앱 내부 ID
- 직전 시스템 질문
- 현재 화면에서 가능한 동작
- 관찰된 UI 요소
- 검증된 상태 값

문맥은 사용자 요청을 대신하지 않는다. 현재 주문이 존재해도 사용자가 취소를 말하지 않았다면 `CANCEL`을 추가하면 안 된다. `available_actions`도 허용 목록일 뿐 실행 지시가 아니다.

## 모델 비교 범위

`configs/model_matrix.json`은 다음 7개를 포함한다.

1. `Qwen/Qwen3.5-0.8B`
2. `Qwen/Qwen3.5-2B`
3. `google/gemma-4-E2B-it`
4. `google/gemma-2-2b-it`
5. `Qwen/Qwen2-1.5B-Instruct`
6. `microsoft/Phi-3-mini-4k-instruct`
7. `TinyLlama/TinyLlama-1.1B-Chat-v1.0`

현재 세 모델의 revision은 실제 Colab smoke run에서 확인한 값을 고정했다. 과거 네 모델은 과거 revision이 완전히 보존되지 않았으므로 첫 재실행에서 resolved commit을 기록하고 이후 고정한다. llama.cpp는 모델이 아니라 엔진이므로 FP16 후보표에 넣지 않는다.

## 실행 순서

1. 데이터 검수: `DRAFT`를 `APPROVED`, `REVISE`, `EXCLUDE`로 판정한다.
2. 7개 모델의 로드·생성 호환성을 소수 gate 사례로 확인한다.
3. 같은 prompt v3, native chat template, greedy decoding, FP16으로 selection 118건을 실행한다.
4. 안전 gate를 먼저 적용한다.
5. 통과 모델의 의미 품질과 자원 사용량을 비교해 주 후보와 경량 후보를 정한다.
6. 주 후보와 Gemma 2 baseline에 기존 48회귀를 실행한다.
7. 후보 1~2개에만 동일 원본 기반 PTQ를 진행한다.

## 후보 판정 규칙

단일 합산 점수로 선정하지 않는다.

1. **안전 gate:** 요청하지 않은 `CANCEL`, `COMMIT_REQUEST`, `RESET`이 한 건이라도 있으면 직접 실행 후보에서 제외한다. 원인 분석·제약 디코딩 후보로는 보존한다.
2. **계약 gate:** code fence만 제거한 뒤 계약 유효율을 본다. 괄호·키·라벨을 사후 복원하지 않는다.
3. **의미 품질:** 전체 의미 exact match, 14의도 macro-F1, fallback exact, 고영향 exact를 함께 본다.
4. **자원:** 로드 시간, 입력·출력 토큰, 생성 시간, GPU peak를 Colab 참고값으로 기록한다. Android 성능으로 해석하지 않는다.
5. **최종 선택:** 안전 gate 통과 모델 중 의미 품질이 높은 모델을 주 후보로 둔다. 품질 차이가 작으면 파일 크기·모바일 실측이 작은 모델을 경량 후보로 남긴다.

모든 모델이 안전 gate를 실패하면 모델을 억지로 선정하지 않는다. 문법 제약, 프롬프트 축소, 지도 미세조정 후 같은 개발 세트를 다시 평가하고, 최종 선택에는 새 독립 test를 사용한다.

## 검증과 채점

```powershell
python scripts/validate_dataset.py data/selection_dev_v0.1.jsonl data/selection_challenge_v0.1.jsonl data/legacy48_regression_v1.2.jsonl
```

예측 파일은 최소한 `case_id`, `raw_output`을 가진 JSONL이다.

```powershell
python scripts/score_predictions.py `
  --gold data/selection_dev_v0.1.jsonl `
  --gold data/selection_challenge_v0.1.jsonl `
  --predictions results/<run>/predictions.jsonl `
  --out-dir results/<run>/scores
```

채점기는 strict JSON과 code-fence 정규화 JSON을 분리하고, 계약 유효율·전체 의미 일치·의도별 F1·fallback·고영향 사례·위험한 추가 행동을 저장한다.

### GPU 없이 실행하는 감사

원본 데이터와 기존 점수를 변경하지 않고 118건의 라우팅 검토표와 gate 검토표를 만든다.

```powershell
python scripts/audit_evaluation.py
python scripts/test_score_predictions_v2.py
python scripts/measure_prompt_tokens.py prompts/prompt_v3_full.txt prompts/prompt_v3_compact.txt `
  --out artifacts/cpu_audit/prompt_size_comparison.json
```

`score_predictions_v2.py`는 기존 채점 결과를 대체하지 않는다. 의도 순서, 요청 수, target, slots, condition, depends_on, fallback을 따로 기록하고 prediction ID 중복을 오류로 보고한다.

CPU 전용 Colab 노트북은 `notebooks/KioGuard_CPU_Analysis_v1.ipynb`이다. Drive의 기존 실험을 읽을 때 결과는 `FP16_COMMON_V3/CPU_ANALYSIS_V1`에 새로 저장한다.

20문장 1차 gate 이후의 오류 진단과 재평가는 다음 파일을 사용한다.

- `artifacts/gate_error_audit/README.md`: 원본 보존 상태와 Gemma 2 사례별 오류 요약
- `scripts/audit_gate_errors.py`: 계약 무효 출력의 내부 의미·안전 오류를 분리하는 보조 진단기
- `scripts/run_qwen35_2b_gguf_case_replay.py`: Qwen3.5 2B FP16·Q4_K_M·Q8_0 사례별 재생 실행기
- `scripts/run_gemma4_e2b_gguf_case_replay.py`: Gemma 4 E2B BF16·Q4_K_M·Q8_0 로컬 사례별 재생 실행기
- `prompts/prompt_v3_1_full.txt`: context 오인, 위험 행동, request 내부 fallback을 보강한 재평가 prompt
- `notebooks/KioGuard_FP16_Gate_Rerun_v3_1.ipynb`: 상위 3개 모델의 새 20문장 gate 실행 노트북
- `artifacts/gate_error_audit/qwen35_2b_v3_1/`: Qwen3.5 2B prompt v3.1 원출력, 채점, 사례별 진단

진단기의 lenient 지표는 strict baseline을 교체하지 않는다. prompt v3.1은 같은 20문장을 보고 수정했으므로 독립 정확도 결과가 아니라 개발 반복 결과로 기록한다.

관련 문서:

- `docs/CPU_AUDIT_AND_NEXT_STEPS.md`
- `docs/PTQ_QAT_EXPERIMENT_PLAN.md`
- `docs/QWEN35_2B_FP16_Q4_Q8_COMPARISON_v0.2.md`
- `docs/GEMMA4_E2B_BF16_Q4_Q8_COMPARISON_v0.1.md`
- `configs/router_policy_v1.json`

## 현재 한계

- 166개 모두 아직 `DRAFT`다.
- 새 118건은 설계용 합성 개발 데이터다.
- 기존 48건의 문맥은 과거 앱에서 복원한 문맥이 아니라 새 평가를 위해 구성한 문맥이다.
- 앱에서 실제로 지원할 동작과 슬롯 이름이 확정되면 일부 정답을 수정해야 한다.
- 7개 모델의 20문장 FP16 개발 gate는 완료했지만 모든 gate를 함께 통과한 모델은 없다. 공통 요약은 `artifacts/fp16_gate_summary_v3.json`에 보존했다.
- 현재 개발 후보 중 Qwen3.5-2B가 계약 유효율과 macro intent F1이 가장 높았지만 위험한 추가 행동 3건과 must-not 위반 1건이 있어 아직 PTQ/QAT 대상으로 확정하지 않는다.
- Qwen3.5-2B의 prompt v3.1 재평가는 계약 유효율 90%, macro intent F1 0.474150, 위험 행동 2건, must-not 위반 1건이었다. 일부 형식·안전 지표는 개선됐지만 의미 품질이 낮아졌고 안전 gate도 실패했으므로 모델·prompt를 아직 확정하지 않는다.
- Gemma 2 2B는 정규화 가능한 JSON을 20/20 생성했으나 각 request 안에 계약에 없는 `fallback` 키를 추가해 계약 유효율이 0%였다. 현재 채점기는 계약 무효 출력을 의도 점수에 포함하지 않으므로 macro F1 0을 의미 이해 능력 0으로 단정하지 않는다.
