# KioGuard 온디바이스 의도분류 연구·실험 종합 보고서

**기준일:** 2026-10-05  
**문서 성격:** 연구 진행·의사결정·재현 근거 통합본  
**대상 범위:** 평가 계약과 데이터 설계, FP16/BF16 모델 선별, GGUF PTQ, 프롬프트 개선, Android 실측 준비  
**현재 결론:** 배포 모델은 아직 확정하지 않았다. 개발용 20건에서는 **Qwen3.5-2B Q4_K_M**이 경량 후보, **Gemma 4 E2B Q8_0**이 품질 보존 후보이다. 166건 사람 검수·확장 평가와 Galaxy S24 Ultra 실측이 남아 있다.

> 이 문서는 저장소의 계획서, 원시·집계 산출물, 실행기, 모델 변환 메타데이터와 Git 커밋 이력을 대조해 작성했다. 퍼센트는 별도 표기가 없으면 20건 개발 게이트의 비율이다. 같은 20건을 보고 프롬프트를 수정한 결과는 독립 정확도가 아니라 개발 회귀 결과로만 해석한다.

---

## 1. 한눈에 보는 현재 상태

| 영역 | 완료 상태 | 확인된 결과 | 아직 필요한 작업 |
|---|---|---|---|
| 출력 계약 | 완료 | 14개 intent와 `requests`·`fallback` 중심의 계약 v3, strict/normalized 채점 분리 | 앱의 실제 target·slot 표준과 최종 대조 |
| 평가 데이터 | 구조 감사 완료 | 선택용 118건 + 회귀 48건 = 166건, 구조 오류 0건 | 166건 모두 `DRAFT`; 사람 검수·승인·동결 필요 |
| FP16 모델 선별 | 1차 게이트 완료 | 7개 모델 중 계약·의미·안전을 모두 통과한 모델 없음 | 독립 test 없이 최종 모델 선정 금지 |
| 오류 분석·프롬프트 | v3.3까지 완료 | Gemma BF16 20건 full exact 45%→75%, high-impact 60%→100%, 안전 위반 0 유지 | 잔여 5건 수정, 프롬프트 비용 축소, 166건 확장 |
| Qwen PTQ | 변환·20건 비교 완료 | Q4 1.222 GiB, full exact 55%, 안전 위반 0; 우선 경량 후보 | v3.3 재검증, 166건, 반복 실행, Android 실측 |
| Gemma PTQ | 로컬 변환·20건 비교 완료 | Q8 4.626 GiB, BF16과 품질 동일; Q4는 안전 회귀로 제외 | Q8 v3.3 재검증, 166건, Android 실측 |
| QAT·증류 | 준비 검토만 완료 | 현재 오류의 큰 부분이 양자화보다 prompt/계약/데이터에서 발생 | 승인 데이터와 독립 test 확보 후 필요성을 다시 판정 |
| Android | 가이드·모델 전달 완료 | Qwen Q4와 Gemma Q8 파일·해시 확보 | S24 Ultra의 지연·메모리·발열·166건 품질 실측 |

이 표의 핵심은 “후보를 만들었다”와 “제품에 넣을 모델을 확정했다”를 구분하는 것이다. 현재 수치는 모델·프롬프트·양자화 형식을 줄이는 개발 근거이며, 실제 앱 정확도와 성능을 확정하는 근거는 아직 아니다. [E01][E02][E14][E15]

## 2. 연구 목표와 판정 원칙

목표는 키오스크·접근성 앱에서 사용자 발화를 구조화된 요청으로 바꾸는 작은 온디바이스 모델을 찾는 것이다. 단순 intent 하나만 맞히는 문제가 아니라 요청 수, 순서, target, slots, 조건, 의존관계, fallback을 함께 보존해야 한다. 특히 사용자가 요청하지 않은 `CANCEL`, `COMMIT_REQUEST`, `RESET`은 데이터 삭제나 결제로 이어질 수 있으므로 일반 정확도보다 먼저 안전 게이트를 적용했다. [E01]

평가 계약 v3의 최상위 키는 `requests`와 `fallback`이다. 각 request에는 `request_id`, `intent`, `target`, `slots`, `condition`, `depends_on`이 들어간다. Markdown code fence 제거 같은 전송 정규화는 허용하지만, 괄호·키·라벨을 의미 추정으로 복원하지 않는다. 채점기는 strict JSON과 normalized JSON을 분리하고, 계약 유효율과 의미 지표를 별도로 기록한다. [E01]

주요 지표의 뜻은 다음과 같다.

| 지표 | 의미 | 해석 시 주의점 |
|---|---|---|
| strict JSON | 모델 원출력이 바로 JSON으로 파싱되는 비율 | 구조 안정성 지표이며 의미 정확도와 다름 |
| 계약 유효율 | JSON이 필수 키와 허용 구조를 지킨 비율 | 계약 무효 출력은 기존 채점에서 의미 점수 0이 될 수 있음 |
| full exact | 요청 수·intent·target·slots·condition·depends_on·fallback이 모두 일치 | 현재 가장 엄격한 사례 단위 성공 기준 |
| Macro intent F1 | 14개 intent의 F1 평균 | 구조·slot·안전 오류를 모두 표현하지 못함 |
| high-impact full exact | 영향도 H 사례의 full exact | 결제·취소·확정·초기화 같은 위험 구간 중심 |
| 위험한 추가 행동 | 요청하지 않은 CANCEL·COMMIT_REQUEST·RESET 등 | 한 건도 직접 실행 후보에서 중대한 문제 |
| must-not 위반 | 정답의 금지 조건을 위반한 사례 | 안전 게이트에 직접 사용 |

## 3. 최초 baseline 계획

초기 계획은 데이터 검수부터 양자화까지 순서를 엄격히 고정했다. [E01][E03]

1. 166건의 `DRAFT`를 사람이 `APPROVED`, `REVISE`, `EXCLUDE`로 검수한다.
2. 7개 모델을 같은 prompt v3, native chat template, greedy decoding, FP16 조건으로 20건 게이트에서 비교한다.
3. 안전·계약·의미 게이트를 통과한 모델만 선택용 118건으로 확장한다.
4. 주 후보와 Gemma 2 baseline에 48건 회귀 평가를 수행한다.
5. 살아남은 1~2개 후보에만 PTQ를 수행한다.
6. PTQ는 기준 정밀도 → Q8_0 → Q6_K → Q5_K_M → Q4_K_M 순서로 내려가며 품질 손실을 확인한다.
7. 반복되는 PTQ 유발 오류가 있을 때만 QAT를 연다. 학습·검증·독립 test를 분리한다.
8. 최종 양자화 후보만 Android에서 실측한다.

초기 안전 규칙은 단일 합산 점수보다 우선했다. 요청하지 않은 위험 행동이 한 건이라도 있으면 직접 실행 후보에서 제외하고, 모든 모델이 실패하면 억지로 하나를 선정하지 않도록 했다. [E01]

## 4. baseline에서 바뀐 점과 변경 이유

| 항목 | 최초 계획 | 실제 진행 | 변경 이유 | 판단에 미친 영향 |
|---|---|---|---|---|
| 사람 검수 순서 | 실험 전에 166건 검수 | 구조 감사 후 166건은 계속 `DRAFT` | 짧은 기간에 모델·하네스 위험을 먼저 파악 | 모든 정확도는 개발 지표로 제한; 최종 일반화 주장 금지 |
| 118건 확장 조건 | 20건 통과 모델만 실행 | 최초 7개 모델이 모두 실패해 118건 미실행 | 안전 게이트 유지 | 모델을 억지로 선정하지 않음 |
| PTQ 시작 조건 | 118건까지 통과한 1~2개 모델 | Qwen3.5-2B와 이후 Gemma 4에 PTQ 수행 | 양자화·엔진 호환성과 모바일 크기 범위를 조기에 파악 | **생산 승인용 절차가 아니라 탐색적 이탈**로 기록 |
| 양자화 단계 | Q8→Q6→Q5→Q4 | 기준 정밀도·Q8·Q4를 직접 비교 | 품질 보존점과 경량 한계를 빠르게 확인 | 중간 비트 최적점은 아직 미검증 |
| 프롬프트 개선 | 통과 실패 시 제약·축소 검토 | v3.1→v3.2→v3.3로 계약·의미 규칙 강화 | 공통 오류가 양자화보다 계약·경계에서 크게 발생 | 20건 점수 개선, 대신 독립성 상실과 입력 비용 증가 |
| Qwen V1 | 최초 GGUF 사례 재생 | 품질 비교에서 무효 처리 | 대화형 배너와 미완료 thinking trace를 예측으로 채점 | V2부터 `--single-turn`, reasoning budget 0, strict 검증 사용 |
| Qwen V3/V3.1 | JSON 완전성 강화 | V3는 nullable 키 누락으로 중단, V3.1 schema sampler 초기화 실패 | llama.cpp 문법 제약과 모델 출력의 호환 문제 | V3.2에서 누락된 nullable 필드만 `null` 보정 |
| Gemma 실행 환경 | Colab 중심 | 로컬 Windows CPU로 이전 | BF16 변환이 RAM 11.50/12.67 GiB에서 `-9` 종료 | Gemma와 Qwen의 절대 시간 직접 비교 금지 |
| Android 절차 | 최종 앱에서 측정 | CLI 1차 → 최소 APK 2차 | 모델 로드·속도·메모리를 앱 개발 전에 분리 측정 | 개발 비용을 줄이고 실패 원인을 분리 |
| Android 사례 수 | 가이드 1차는 20건 | 사용자는 166건 실측을 계획 | 개발 회귀를 넘어 전체 초안을 확인하려는 요구 | 실행 전에 166건 검수·입력 하네스 범위를 명시해야 함 |

가장 큰 절차 변경은 PTQ를 원래 예정 시점보다 먼저 수행한 것이다. 이는 “Qwen 또는 Gemma를 배포 승인했다”는 뜻이 아니다. 양자화 파일이 실제로 생성·로드되는지, Q4와 Q8의 손실 양상이 모델별로 어떻게 다른지, Galaxy S24 Ultra에 올릴 파일 크기가 현실적인지를 알아보기 위한 기술 탐색이었다. 최종 승격 조건인 사람 검수·독립 test·Android 실측은 그대로 남아 있다. [E03][E09][E11][E14]

## 5. 평가 데이터 설계와 감사 결과

### 5.1 데이터 구성과 동일성

| 파일 | 사례 수 | 용도 | SHA-256 |
|---|---:|---|---|
| `selection_dev_v0.1.jsonl` | 84 | 14개 intent별 핵심 개발 사례 | `fc45104a62fb8b6781ad78c8931bed9434cff797f3e39af8fca593bf8d2d5c46` |
| `selection_challenge_v0.1.jsonl` | 34 | 모호성·부정·조건·복합·문맥 대조 | `bf5a02d0fe0dd470083ffc4861fce90daf4dedddaee66617a82343bb58e9f4b0` |
| `legacy48_regression_v1.2.jsonl` | 48 | 기존 발화의 새 계약 회귀 세트 | `7c4f55a446201d3dc0fdf0a65cb0e9d4bd455cd10a6e4e9192735c1decf5b8e0` |
| `evaluation_review_v0.1.csv` | 166 | 사람 검수용 평면 표 | `7c6e85779b2cbe303e633c8fe031f739f212b2adca10b27f7bda80e961821c3f` |

해시는 2026-10-05 현재 저장소 파일에서 다시 계산했다. 선택용 118건은 84+34이고, 여기에 48건 회귀를 더하면 전체 검토 범위는 166건이다. 검수표의 166행은 모두 `DRAFT`이다. [E01][E04]

### 5.2 118건의 분포

| 구분 | 수량 |
|---|---:|
| 영향도 H / M / L / U | 30 / 55 / 26 / 7 |
| 복잡도 C1 / C2 / C3 / CU | 59 / 41 / 17 / 1 |
| LLM_REQUIRED / ROUTER_REVIEW / RULE_CANDIDATE | 49 / 24 / 45 |
| 조건 포함 | 4 |
| 복합 요청 | 9 |
| 요청과 fallback 동시 검토 | 5 |
| 사람 검수 대기 | 118 |
| 구성된 문맥 사용 | 118 |

라우팅 분류는 학습된 라우터의 정확도가 아니다. 영향도 H, 복잡도 C3/CU, fallback, 복합·조건 요청은 LLM을 요구하고, L/M·C1·단일 요청·fallback 없음만 규칙 후보로 둔 보수적 검토 제안이다. 현재 앱 구조를 설계할 때 “45건은 규칙 후보, 49건은 LLM 필요, 24건은 추가 검토”라는 작업량 추정에는 쓸 수 있지만 실제 라우팅 성능으로 인용하면 안 된다. [E04][E05]

### 5.3 의도적으로 유지한 중복 발화

같은 문자열이라도 문맥에 따라 결과가 달라지는지 보기 위해 `네` 6건, `아니요` 3건, `카드로 결제할게요` 3건, `아메리카노 한 잔이요` 2건, `영수증은 안 받을게요` 2건을 유지했다. 단순 중복 제거를 하면 확인·거절·결제 문맥 대조가 사라진다. [E04]

## 6. prompt v3와 CPU 감사

원본 prompt v3는 1,873자, compact 후보는 1,416자로 24.4% 짧았다. 문자 기반 proxy는 791에서 532로 32.7% 감소했다. 이 proxy는 모델 tokenizer의 실제 토큰 수가 아니므로 속도나 context 절감률로 직접 해석하지 않았다. compact prompt는 정확도·안전 A/B를 통과하지 않았기 때문에 원본을 대체하지 않았다. [E05][E06]

CPU 감사에서는 원본 데이터와 기존 결과를 바꾸지 않고 118건 라우팅 검토표, 20건 게이트 검토표, slot·target 목록, 세부 채점기 v2를 만들었다. 이는 GPU 없이 데이터 구조와 평가 논리를 검증하기 위한 단계였다. [E05]

## 7. 7개 모델 FP16 20건 baseline

최초 공통 게이트는 Colab Tesla T4에서 모델마다 20건을 실행했다. 시간과 GPU 메모리는 Android 성능이 아니라 당시 개발 환경 참고값이다. [E07]

| 모델 | 계약 유효 | Macro F1 | fallback exact | full exact | 위험 행동 | must-not | 평균 생성 | GPU peak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Qwen3.5-0.8B | 0% | 0.0000 | 0% | 0% | 0 | 0 | 7.90초 | 1.72 GiB |
| Qwen3.5-2B | 80% | 0.6643 | 75% | 0% | 3 | 1 | 6.20초 | 4.26 GiB |
| Gemma 4 E2B | 5% | 0.0714 | 5% | 0% | 0 | 0 | 7.23초 | 9.64 GiB |
| Gemma 2 2B | 0% | 0.0000 | 0% | 0% | 0 | 0 | 5.45초 | 5.10 GiB |
| Qwen2-1.5B | 95% | 0.2036 | 80% | 0% | 2 | 2 | 3.57초 | 3.03 GiB |
| Phi-3 Mini | 65% | 0.5119 | 55% | 0% | 1 | 2 | 5.09초 | 7.92 GiB |
| TinyLlama-1.1B | 0% | 0.0000 | 0% | 0% | 0 | 0 | 7.30초 | 3.04 GiB |

결론은 `NO_MODEL_SELECTED`였다. Qwen3.5-2B가 계약과 intent F1의 가장 강한 후보였지만 위험 행동 3건과 must-not 1건 때문에 직접 실행 후보가 될 수 없었다. Qwen2는 계약 유효율 95%였어도 의미와 안전이 낮았다. Gemma 2의 0% 계약은 모든 request 안에 허용되지 않은 `fallback` 키를 추가한 영향이므로 “의미 이해가 0”이라고 단정하지 않았다. [E07]

## 8. prompt v3.1 재평가와 모델 범위 확장

v3.1은 context를 실행 지시로 오인하는 문제, request 내부 fallback, 위험 행동 경계를 강화했다. 동일한 20건을 사용했으므로 개선 개발용 회귀다. Gemma 3 1B를 추가해 8개 후보를 확인했다. [E08]

| 모델 | 계약 유효 | full exact | Macro F1 | 위험 행동 | must-not | 판정 |
|---|---:|---:|---:|---:|---:|---|
| Gemma 2 2B | 65% | 5% | 0.4881 | 1 | 1 | 미승격 |
| Gemma 3 1B | 70% | 5% | 0.2143 | 2 | 2 | 미승격 |
| Gemma 4 E2B | 85% | 5% | 0.8452 | 1 | 2 | 품질 강점, 안전 실패 |
| Phi-3 Mini | 70% | 0% | 0.5884 | 1 | 2 | 미승격 |
| Qwen2-1.5B | 85% | 0% | 0.3313 | 2 | 2 | 미승격 |
| Qwen3.5-0.8B | 65% | 5% | 0.1190 | 0 | 1 | must-not 실패 |
| Qwen3.5-2B | 90% | 15% | 0.4741 | 2 | 1 | 구조 개선, 안전 실패 |
| TinyLlama-1.1B | 0% | 0% | 0.0000 | 0 | 0 | 계약 실패 |

Gemma 4는 Macro F1 0.8452로 의미 잠재력이 높았고, Qwen3.5-2B는 계약 90%와 full exact 15%로 구조가 상대적으로 안정적이었다. 어느 모델도 안전 게이트를 완전히 통과하지 않아 118건으로 확장하지 않았다. 이후 PTQ는 이 둘을 생산 승인하기 위해서가 아니라 “강한 개발 후보가 양자화에서 어떻게 변하는지” 확인하기 위해 수행했다. [E08][E03]

## 9. Qwen3.5-2B PTQ와 사례 재생

### 9.1 변환과 파일 크기

Qwen 원본은 `Qwen/Qwen3.5-2B`, revision `15852e8c16360a2fea060d615a32b45270f8a8fc`로 고정했다. llama.cpp commit은 `b04642061d183dff8504127dfbee1c1a8352682c`이다. Colab에서 HF 4,571,277,391 bytes를 F16 GGUF 3,897,387,936 bytes로 변환한 뒤 Q8_0 2,076,674,976 bytes와 Q4_K_M 1,312,164,768 bytes를 생성했다. 다운로드 128.64초를 포함한 전체 변환은 532.54초였다. 이 단계는 변환 성공 기록이며 정확도나 Android 성능을 뜻하지 않는다. [E09]

### 9.2 V1을 무효 처리한 이유

최초 사례 재생 V1은 `llama-cli`의 대화형 배너와 완료되지 않은 thinking trace가 예측으로 채점됐다. 숫자가 만들어졌더라도 모델의 최종 JSON 응답을 비교한 것이 아니므로 품질 근거에서 제외했다. V2는 `--single-turn`, `--reasoning-budget 0`, strict JSON 검증을 도입하고 첫 사례가 유효 JSON이 아니면 즉시 실패하도록 바꿨다. 이 조치는 낮은 점수를 숨기기 위한 후처리가 아니라 실행 경로가 실제 단일 응답을 채점하도록 바로잡은 것이다. [E10]

### 9.3 V2 유효 baseline

| 형식 | 계약 유효 | full exact | Macro F1 | high-impact | 위험 / must-not | 평균 생성/유효 건 |
|---|---:|---:|---:|---:|---:|---:|
| F16 | 80% | 15% | 0.3908 | 0% | 2 / 1 | 138.69초 |
| Q4_K_M | 75% | 10% | 0.3122 | 0% | 2 / 1 | 96.56초 |
| Q8_0 | 80% | 15% | 0.3908 | 0% | 2 / 1 | 121.63초 |

Q8은 사례별로 F16을 보존했고, Q4는 `CH-CLR-01` 한 건의 추가 회귀가 있었다. 그러나 세 형식 모두 high-impact 0%, 위험 행동 2건, must-not 1건이므로 배포 판단에는 부족했다. [E10]

### 9.4 prompt v3.2와 실행기 수정

v3.2는 fallback을 intent로 만들지 않기, target·slot 환각 금지, 부정 범위, 복합 요청, `COMMIT_REQUEST` 경계를 강화했다. 실행 V3은 `DEV-FUL-01`에서 nullable `condition`, `depends_on` 누락으로 중단됐다. V3.1은 llama.cpp JSON Schema sampler 초기화 오류로 실행되지 않았다. V3.2 실행기는 의미 값을 추론하지 않고 누락된 두 nullable request 필드만 `null`로 넣은 다음 계약을 검사했다. 나중 사례에서 계약 오류가 나더라도 전체 비교를 끝내도록 continuation도 수정했다. 관련 변경은 `b1558ab`, `3f62ee5`, `b9c24c1`, `1d68a5c`에 기록돼 있다. [E11][E18]

### 9.5 Qwen V3.2 최종 20건 결과

| 지표 | F16 | Q4_K_M | Q8_0 |
|---|---:|---:|---:|
| 파일 크기 | 3.630 GiB | 1.222 GiB | 1.934 GiB |
| 기준 대비 감소 | - | 66.3% | 46.7% |
| 평균 생성/유효 건 | 195.38초 | 117.42초 | 172.79초 |
| 프로세스 성공 | 18/20 | 19/20 | 18/20 |
| strict JSON | 95% | 100% | 95% |
| 계약 유효 | 90% | 95% | 90% |
| 요청 수 일치 | 75% | 80% | 80% |
| intent multiset | 70% | 70% | 70% |
| target | 70% | 70% | 70% |
| slots | 35% | 55% | 35% |
| fallback | 80% | 85% | 85% |
| full exact | 35% (7/20) | **55% (11/20)** | 35% (7/20) |
| Macro intent F1 | **0.8095** | 0.6786 | 0.7976 |
| high-impact full exact | 20% | **40%** | 20% |
| 위험 행동 / must-not | **0 / 0** | **0 / 0** | 1 / 1 |

Q4는 FP16보다 작고 이 CPU 재생에서 평균 생성 시간이 39.9% 짧았다. `DEV-PAY-01`, `DEV-REC-01`, `CH-NEG-01`, `CH-NEG-02`를 추가로 회복했으며 FP16 대비 full-exact 회귀가 없었다. 다만 Macro F1은 F16보다 낮아 “모든 지표에서 Q4가 더 정확하다”는 결론은 아니다. Q8은 full-exact가 F16과 같았지만 `CH-NEG-02`에서 금지된 `CANCEL`을 추가해 안전 보존에 실패했다. [E11]

세 형식이 함께 실패한 9건은 `DEV-FUL-01`, `DEV-BEN-01`, `DEV-NAV-01`, `DEV-CAN-01`, `DEV-UI-01`, `DEV-HEL-01`, `DEV-COM-01`, `DEV-RES-01`, `CH-MUL-01`이었다. 주된 병목은 slots, intent 경계와 복합 요청 분해였다. [E11]

### 9.6 V2에서 V3.2로 변한 수치

| 형식 | full exact | Macro F1 | 계약 유효 | high-impact | 위험 / must-not |
|---|---:|---:|---:|---:|---:|
| F16 | 15%→35% | 0.3908→0.8095 | 80%→90% | 0%→20% | 2/1→0/0 |
| Q4_K_M | 10%→55% | 0.3122→0.6786 | 75%→95% | 0%→40% | 2/1→0/0 |
| Q8_0 | 15%→35% | 0.3908→0.7976 | 80%→90% | 0%→20% | 2/1→1/1 |

이 개선은 같은 20건을 분석해 prompt와 실행기를 고친 결과다. 따라서 “미지의 사용자 발화 정확도가 55%”가 아니라 “개발 회귀 20건 중 11건이 전체 구조까지 일치했다”라고 표현해야 한다. [E11]

## 10. Gemma 4 E2B PTQ와 사례 재생

### 10.1 Colab 실패와 로컬 전환

Gemma 원본은 `google/gemma-4-E2B-it`, revision `3e22461f65e89153144f8adb70e3b8c2cc9845a7`로 고정했다. Colab에서는 10.28GB snapshot 다운로드 후 `convert_hf_to_gguf.py --use-temp-file`이 58.51초 뒤 `-9`로 종료됐다. 관측 RAM은 11.50/12.67 GiB였고 GGUF가 생성되지 않았다. 이는 모델 품질이나 llama.cpp 비호환 결과가 아니라 host RAM 한계로 분류했다. [E12]

로컬 Windows CPU와 llama.cpp `7fe450e19`에서 BF16 GGUF를 만든 뒤 같은 원본에서 Q4_K_M과 Q8_0을 생성했다. [E13]

| 형식 | bytes | GiB | SHA-256 | BF16 대비 감소 |
|---|---:|---:|---|---:|
| BF16 | 9,311,305,152 | 8.672 | `79bd7b9ee0b3cfb736fdbb32de560f3bd97e68bbebfbecea6b5f7262bde34855` | - |
| Q4_K_M | 3,427,880,384 | 3.192 | `bf3ba4103f292b1fc4c46b6f5b8e61dd53dd00558fe57334152635c5ec255bf1` | 63.19% |
| Q8_0 | 4,967,497,152 | 4.626 | `4b9e6317389d66a2a8d6fb4a6fd1dda89915906752a8e3807a1c4014dd3133b4` | 46.65% |

### 10.2 Gemma prompt v3.2 20건 결과

| 지표 | BF16 | Q4_K_M | Q8_0 |
|---|---:|---:|---:|
| 평균 생성/유효 건 | 48.98초 | 36.04초 | 55.39초 |
| 프로세스 성공 | 17/20 | 19/20 | 17/20 |
| strict JSON | 95% | 100% | 95% |
| 계약 유효 | 85% | 95% | 85% |
| 요청 수 일치 | 85% | 70% | 85% |
| intent multiset | 80% | 60% | 80% |
| target | 75% | 50% | 75% |
| slots | 55% | 40% | 55% |
| fallback | 85% | 80% | 85% |
| full exact | 45% (9/20) | **20% (4/20)** | 45% (9/20) |
| Macro intent F1 | 0.8333 | 0.7429 | 0.8333 |
| high-impact full exact | 60% | **0%** | 60% |
| 위험 행동 / must-not | 0 / 0 | **4 / 3** | 0 / 0 |

Q8은 20건의 사례별 판정과 모든 집계 품질 지표가 BF16과 같아 품질 보존 후보가 됐다. 반면 Q4는 파일 63.19% 절감과 로컬 CPU 시간 26.4% 단축이 있었지만 full exact가 25%p, high-impact가 60%p 하락했다. `DEV-REC-01`에서 영수증 대신 `COMMIT_REQUEST`, `DEV-BEN-01`에서 추가 `COMMIT_REQUEST`, `DEV-RES-01`에서 `RESET` 앞에 `CANCEL`, `CH-NEG-01`에서 금지된 `CANCEL`을 만들었다. 안전 게이트 때문에 Gemma Q4는 현재 후보에서 제외한다. [E13][E14]

BF16과 Q8이 함께 맞힌 9건은 `DEV-SEL-01`, `DEV-REC-01`, `DEV-NAV-01`, `DEV-GUI-01`, `DEV-INF-01`, `DEV-RES-01`, `CH-CLR-02`, `CH-NEG-01`, `CH-MUL-01`이다. 세 형식 공통 실패는 10건으로, 양자화 이전부터 prompt·모델 오류가 남아 있음을 보여준다. [E14]

## 11. Qwen과 Gemma의 양자화 반응 비교

같은 20건과 prompt v3.2를 사용했지만 Qwen은 Colab CPU/llama.cpp `b046...`, Gemma는 로컬 Windows CPU/`7fe450e19`에서 실행했다. 품질 지표는 같은 정답과 채점기를 사용하므로 비교할 수 있지만 절대 시간은 직접 비교하면 안 된다. [E11][E14]

| 모델·형식 | 크기 | 계약 | full exact | Macro F1 | high-impact | 위험 / must-not |
|---|---:|---:|---:|---:|---:|---:|
| Gemma BF16 | 8.672 GiB | 85% | 45% | 0.8333 | 60% | 0 / 0 |
| Gemma Q8_0 | 4.626 GiB | 85% | 45% | 0.8333 | 60% | 0 / 0 |
| Gemma Q4_K_M | 3.192 GiB | 95% | 20% | 0.7429 | 0% | 4 / 3 |
| Qwen F16 | 3.630 GiB | 90% | 35% | 0.8095 | 20% | 0 / 0 |
| Qwen Q8_0 | 1.934 GiB | 90% | 35% | 0.7976 | 20% | 1 / 1 |
| Qwen Q4_K_M | **1.222 GiB** | **95%** | **55%** | 0.6786 | 40% | **0 / 0** |

Q4라는 이름이 같아도 손실은 모델별로 달랐다. Qwen Q4는 이 개발 게이트에서 사례 회복이 있었고, Gemma Q4는 안전 회귀가 발생했다. 따라서 “4비트는 정확도가 항상 크게 떨어진다” 또는 “Q4가 Q8보다 더 정확하다”라는 일반화는 근거가 없다. 현재 데이터가 말해 주는 범위는 Qwen3.5-2B의 이 변환·prompt·20건 조합에서는 Q4가 경량 후보였고, Gemma 4에서는 Q8만 기준 품질을 보존했다는 것이다. [E11][E14]

## 12. prompt v3.3 공통 실패 개선

Qwen의 공통 실패 9건과 Gemma의 공통 실패 10건을 비교해 두 모델이 함께 틀린 6건을 찾았다: `DEV-FUL-01`, `DEV-BEN-01`, `DEV-CAN-01`, `DEV-UI-01`, `DEV-HEL-01`, `DEV-COM-01`. 원인을 값 없는 slot 추가, target 정규화, intent 경계, fallback·부정·계약, 확인값 매핑으로 나눴다. [E15]

v3.3은 다음 규칙을 추가·강화했다.

- 발화·검증 문맥에 없는 `null`·unknown slot을 만들지 않는다.
- NAVIGATE target은 `APP_UI`, 일반 HELP target은 `CURRENT_TASK`로 정규화한다.
- 항목 제거는 CANCEL, 전체 초기화는 RESET로 경계를 명확히 한다.
- 모호한 발화를 HELP/INFO 실행으로 바꾸지 않고 fallback을 사용한다.
- 부정된 행동을 요청으로 만들지 않는다.
- 확인 응답의 action과 confirmation 값을 분리한다.
- 모든 필수 키를 출력하고 request 내부에 fallback을 넣지 않는다.

### 12.1 Gemma BF16 v3.2→v3.3 변화

| 지표 | v3.2 | v3.3 | 변화 |
|---|---:|---:|---:|
| strict JSON | 95% | 90% | -5%p |
| 계약 유효 | 85% | 90% | +5%p |
| intent multiset | 80% | 85% | +5%p |
| target | 75% | 90% | +15%p |
| slots | 55% | 75% | +20%p |
| full exact | 45% (9/20) | **75% (15/20)** | **+30%p** |
| Macro F1 | 0.8333 | **0.8810** | +0.0476 |
| high-impact | 60% | **100%** | +40%p |
| 위험 행동 / must-not | 0 / 0 | 0 / 0 | 유지 |

회복 6건은 `DEV-MOD-01`, `DEV-PAY-01`, `DEV-HEL-01`, `DEV-COM-01`, `CH-NEG-02`, `CH-CTX-04`이고 기존 정답의 full-exact 회귀는 없었다. 잔여 실패는 `DEV-FUL-01`, `DEV-BEN-01`, `DEV-CAN-01`, `DEV-UI-01`, `CH-CLR-01`이다. [E15]

품질 비용도 증가했다. Gemma tokenizer 기준 prompt는 2,407→3,027 tokens로 620 tokens, 25.8% 늘었다. 평균 유효 출력 생성 시간은 48.98→66.17초로 약 35.1% 늘었다. strict JSON은 5%p 낮아졌지만 계약과 의미는 개선됐다. v3.3은 사전 승격 조건인 위험 0, must-not 0, high-impact 60% 이상, 계약 85% 이상을 충족했으나 사용자 결정에 따라 166건 실행은 시작하지 않았다. [E15][E16]

## 13. QAT와 지식 증류를 지금 바로 하지 않은 이유

QAT는 FP16에서 맞던 사례가 PTQ에서 반복적으로 틀릴 때 적합하다. 이번 결과에서는 Gemma Q4의 명확한 양자화 회귀가 있지만, Gemma Q8이 품질을 보존했고 Qwen의 공통 오류 상당수가 prompt v3.3에서 회복됐다. 데이터 166건도 모두 검수 전이다. 이 상태에서 QAT를 시작하면 잘못된 정답과 이미 prompt로 해결 가능한 오류를 학습할 위험이 있다. [E12][E14][E15]

지식 증류와 양자화는 함께 사용할 수 있다. 큰 교사 모델이 승인된 학습 데이터를 라벨링하거나 작은 학생 모델을 지도하고, 학생을 다시 Q4/Q8로 양자화할 수 있다. 다만 현재 166건은 규모가 작고 독립 test가 없으며, 교사 출력도 사람 검수가 필요하다. 우선순위는 ① 정답 검수, ② 독립 test 분리, ③ prompt·하네스 안정화, ④ 후보별 Android 실측, ⑤ 그래도 남는 양자화 유발 오류에 QAT/증류 순서다. [E03][E12]

## 14. 모델 파일 전달과 재현 정보

Android 팀 전달용 모델은 GitHub에 올리지 않고 Google Drive로 전달했다. GGUF는 수 GB여서 Git 저장소의 코드·문서 이력과 분리한다. [E17]

| 후보 | 파일 | bytes | SHA-256 | 전달 위치 |
|---|---|---:|---|---|
| Qwen3.5-2B Q4_K_M | `qwen35-2b-q4_k_m.gguf` | 1,312,164,768 | `9ace65e67f4d3863729ad4f50ca97aedb734fcdbf6161656fc00028ba3ddf832` | [Google Drive](https://drive.google.com/file/d/1s5soutguQn4auPdOD08HwS21Tc-UBALT/view) |
| Gemma 4 E2B Q8_0 | `gemma-4-E2B-it-q8_0.gguf` | 4,967,497,152 | `4b9e6317389d66a2a8d6fb4a6fd1dda89915906752a8e3807a1c4014dd3133b4` | [Google Drive](https://drive.google.com/file/d/1cwoElzKDJXbeSw5IWX85gPT3oI2yev73/view) |

Qwen 파일은 Colab 임시 저장소의 변환 산출물을 Drive `KioGuard/models`로 복사한 뒤 원본과 Drive 사본의 크기·SHA-256 일치를 확인했다. Gemma Q8 해시는 로컬 PTQ 메타데이터와 동일하다. 두 링크는 현재 비공개 Drive 권한이므로 팀원이 접근하려면 공유 권한을 별도로 부여해야 한다. 영구 근거는 `model_delivery_manifest_20261005.json`에 함께 기록한다. [E13][E17]

## 15. Android 실측 계획과 현재 공백

Galaxy S24 Ultra 실측은 완성 앱 없이도 시작할 수 있다. 1차는 Android NDK로 `llama.cpp`의 `llama-bench`와 추론 CLI를 `arm64-v8a`로 빌드해 ADB로 전송한다. 2차는 1차에서 살아남은 1~2개 모델만 최소 APK에 연결한다. [E02]

두 모델을 같은 Android llama.cpp commit에서 실행해야 엔진 차이를 제거할 수 있다. 시작 후보는 Gemma 지원이 확인된 `7fe450e19`이며, Qwen이 로드되지 않으면 두 모델을 함께 지원하는 하나의 commit으로 전체를 다시 실행한다. [E02]

측정 항목은 다음과 같다.

1. 모델 파일 크기와 SHA-256, 로드 성공 여부
2. `llama-bench`의 prompt processing과 token generation 처리량
3. process-cold 첫 실행과 warm 반복
4. 실제 prompt v3.3 종단 간 지연 p50·p95
5. peak RSS/VmHWM/PSS와 OOM·LMK 여부
6. 배터리·thermalservice 원문과 스로틀링
7. 원시 JSON, 계약 유효율, full exact, Macro F1, 위험 행동

가이드의 1차 종단 간 검증은 기존 20건을 기준으로 작성됐다. 사용자는 166건 측정을 계획하므로 실제 실행 전 다음을 보완해야 한다: 166건의 검수 상태 확정, 48건과 118건의 입력 렌더링 통합, 모델별 native chat template 유지, 중단·재개와 로그 스키마, 배터리·발열 때문에 장시간 실행을 여러 세션으로 나누는 기준. 현재 Android 지연·메모리·발열 수치는 **0건**이며, Colab/PC 시간으로 대신할 수 없다. [E02]

## 16. 앱 용량과 권장 아키텍처

Qwen Q4와 Gemma Q8을 둘 다 앱에 넣으면 모델만 약 5.85 GiB가 된다. 작은 앱 목표와 맞지 않는다. 최종 앱은 두 모델을 내장하기보다 한 모델을 선택하고, 가능하면 설치 후 선택 다운로드나 온디맨드 asset으로 배포해야 한다.

현재 근거로는 다음 구조가 합리적이다.

- 명확하고 저위험한 단일 요청은 규칙 또는 작은 분류기로 처리한다.
- 모호성·조건·복합 요청·고영향 요청만 LLM으로 보낸다.
- 위험 행동은 모델 출력만으로 즉시 실행하지 않고 앱 상태 검증과 사용자 확인을 거친다.
- 모델은 한 개만 기본 후보로 두고 Android 실측 후 교체 가능하게 만든다.
- 경량 우선이면 Qwen Q4 1.222 GiB, 개발 게이트 품질 보존 우선이면 Gemma Q8 4.626 GiB를 비교한다.

118건의 라우팅 제안은 이 구조의 출발점일 뿐 성능 검증은 아니다. 실제 앱에서는 규칙 커버리지, LLM 호출률, 실패 fallback, 사용자 확인율을 별도로 측정해야 한다. [E04]

## 17. 완료된 작업의 시간순 기록

| 날짜 | 작업 | 핵심 근거·커밋 |
|---|---|---|
| 09-28 | 계약 v3 평가 데이터·7모델 matrix 작성 | `ff8a5b9` |
| 09-28 | CPU 감사, 라우팅 제안, PTQ/QAT 계획 | `dddb156` |
| 09-29 | 7모델 FP16 게이트 완료, 미선정 판정 | `56e5802`, `1f096d9` |
| 09-30~10-01 | v3.1 오류 분석·후보 재실행 | `03d5258`, `a98959f`, `e8ade6c`, `5a1527e`, `dab99ff` |
| 10-01 | Qwen PTQ 변환·게이트, Gemma RAM 한계 기록 | `96aaf11`, `998a5e6`, `95d9605`, `fbb99f8` |
| 10-02~10-03 | 재개 가능한 GGUF 사례 실행기, UTF-8·noninteractive 수정 | `7a539f9`, `15352f7`, `06d929f`, `db85202` |
| 10-03 | Qwen V2 유효 비교와 prompt v3.2 강화 | `25f7f0d`, `b1558ab` |
| 10-04 | nullable·continuation 수정, Qwen V3.2 완료 | `3f62ee5`, `b9c24c1`, `1d68a5c`, `68e431b` |
| 10-05 | Gemma 로컬 PTQ·BF16/Q4/Q8 비교 | `b15274d` |
| 10-05 | prompt v3.3 공통 실패 개선 | `ee49f6e` |
| 10-05 | Galaxy S24 Ultra 실측 가이드 | `fa9d5c0` |

커밋은 결과만이 아니라 왜 하네스가 바뀌었는지 추적하는 근거다. 예를 들어 V1 무효화 후 noninteractive 검증, V3 schema 실패 후 제한적 nullable 보정, 중간 실패 후 continuation이 각각 별도 커밋으로 남아 있다. [E18]

## 18. 현재 후보 판정

### 18.1 경량 후보: Qwen3.5-2B Q4_K_M

- 1.222 GiB로 두 실측 후보 중 작다.
- prompt v3.2 20건에서 계약 95%, full exact 55%, high-impact 40%, 위험·must-not 0건이다.
- F16 대비 크기 66.3% 감소, 해당 CPU 재생에서는 평균 시간 39.9% 감소다.
- Macro F1 0.6786으로 F16 0.8095보다 낮고, v3.3 Qwen 재평가와 독립 test가 없다.

따라서 “가장 정확한 모델”이 아니라 **현재 가장 작은 Android 우선 실측 후보**다. [E11]

### 18.2 품질 보존 후보: Gemma 4 E2B Q8_0

- 4.626 GiB로 크지만 BF16보다 46.65% 작다.
- prompt v3.2 20건에서 BF16과 사례·집계 품질이 같았다: full exact 45%, Macro F1 0.8333, high-impact 60%, 안전 위반 0.
- v3.3 BF16은 full exact 75%, high-impact 100%까지 개선됐지만 Q8 v3.3 재실행은 아직 없다.
- 로컬 CPU에서 Q8이 BF16보다 13.1% 느렸으며 Android에서도 느릴지는 모른다.

따라서 **품질 보존 가능성이 확인된 Android 비교 후보**이며, 앱 용량을 수용할 가치가 있는지는 S24 실측이 결정한다. [E13][E14][E15]

### 18.3 제외: Gemma 4 E2B Q4_K_M

full exact 20%, high-impact 0%, 위험 행동 4건, must-not 3건 때문에 현재 배포 후보에서 제외한다. 작은 크기와 빠른 로컬 CPU만으로 안전 게이트를 상쇄하지 않는다. [E14]

## 19. 남은 작업과 권장 순서

1. **166건 사람 검수:** `APPROVED/REVISE/EXCLUDE`, target·slot·fallback 기준을 확정한다.
2. **평가 동결:** 승인된 개발 세트와 별도 비공개 독립 test를 분리하고 SHA-256을 기록한다.
3. **v3.3 하네스 통일:** Qwen Q4와 Gemma Q8에 같은 계약·채점기를 적용한다. Android에서는 같은 llama.cpp commit을 사용한다.
4. **166건 개발 평가:** 중단·재개 가능한 방식으로 두 후보를 실행하고 118/48을 나눠 보고한다.
5. **사례별 전후 분석:** baseline 정밀도 대비 양자화 회귀·회복·공통 오류를 분리한다.
6. **Galaxy S24 Ultra 실측:** 로드, p50/p95, peak RSS/PSS, 발열, 배터리, 166건 JSON 품질을 수집한다.
7. **최종 후보 선택:** 안전 → 품질 → 메모리·속도·용량 순으로 판단한다.
8. **최소 APK:** 선택한 1~2개만 앱 lifecycle·JNI·백그라운드 복귀까지 확인한다.
9. **QAT/증류 재판정:** 승인 데이터와 독립 test에서 양자화 유발 회귀가 반복될 때만 파일럿을 연다.

실측을 먼저 수행할 수는 있지만, 검수되지 않은 166건 결과는 개발 지표로만 보고해야 한다. 일정이 촉박하면 Android의 20건 실행·성능 계측을 먼저 완료하고, 166건은 검수 후 이어가는 두 단계가 가장 안전하다. [E02][E15]

## 20. 제한사항과 잘못 해석하기 쉬운 지점

1. 20건은 모델·프롬프트를 반복 개선한 개발 게이트다. 55%·75%를 서비스 정확도로 부르면 안 된다.
2. 166건도 모두 `DRAFT`이며 독립 test가 아니다.
3. 계약 무효 출력에 0점을 주는 방식은 의미 잠재력을 과소평가할 수 있지만, 앱 통합에서는 계약 실패 자체가 실제 실패다.
4. Qwen과 Gemma의 절대 생성 시간은 실행 환경과 llama.cpp commit이 달라 직접 비교할 수 없다.
5. PC/Colab CPU 시간은 Galaxy S24 Ultra 지연·발열·메모리를 예측하지 않는다.
6. Q4/Q8의 결과는 모델·변환기·프롬프트·커널에 의존한다. bit 수만으로 품질을 일반화할 수 없다.
7. v3.3 개선은 같은 20건에 맞춘 결과여서 과적합 가능성이 있다.
8. Drive 모델 링크의 접근 권한은 별도 공유 설정에 의존한다.
9. QAT나 증류는 잘못된 정답·안전 규칙을 자동으로 해결하지 않는다.

## 21. 재현 설정 요약

| 항목 | Qwen V3.2 | Gemma V1 / v3.3 |
|---|---|---|
| 모델 | Qwen/Qwen3.5-2B | google/gemma-4-E2B-it |
| revision | `15852e8c...a8fc` | `3e22461f...45a7` |
| llama.cpp | `b0464206...682c` | `7fe450e19` |
| prompt v3.2 hash | `d58f06ac...308b` | 동일 |
| prompt v3.3 hash | 미실행 | `b56fae38...9466b` |
| seed | 20260930 | 20260930 |
| GPU layers | 0 | 0 |
| context | 8192 | 4096 |
| max new tokens | 220 | 220 |
| 채점 | scorer v2, strict/normalized 분리 | 동일 |

## 22. 근거 색인

| ID | 근거 파일 | 뒷받침하는 내용 |
|---|---|---|
| E01 | [`evaluation/README.md`](../README.md) | 계약 v3, 데이터 구성, baseline 순서, 안전·계약·의미 판정 규칙, 현재 한계 |
| E02 | [`ANDROID_S24_ON_DEVICE_BENCHMARK_GUIDE_v0.1.md`](ANDROID_S24_ON_DEVICE_BENCHMARK_GUIDE_v0.1.md) | S24 Ultra CLI/APK 절차, 측정 항목, 완료·중단 조건 |
| E03 | [`PTQ_QAT_EXPERIMENT_PLAN.md`](PTQ_QAT_EXPERIMENT_PLAN.md) | PTQ 순서, QAT 시작 조건, 원래 승격 절차 |
| E04 | [`dataset_audit_summary.json`](../artifacts/cpu_audit/dataset_audit_summary.json) | 118건 영향도·복잡도·라우팅·자동 플래그·중복 발화 |
| E05 | [`CPU_AUDIT_AND_NEXT_STEPS.md`](CPU_AUDIT_AND_NEXT_STEPS.md) | CPU 감사 결과, 166건 구조 검증, 라우팅 권고 성격 |
| E06 | [`prompt_size_comparison.json`](../artifacts/cpu_audit/prompt_size_comparison.json) | v3와 compact 정적 크기, proxy 한계 |
| E07 | [`fp16_gate_summary_v3.json`](../artifacts/fp16_gate_summary_v3.json) | 최초 7모델 FP16 게이트 수치와 `NO_MODEL_SELECTED` |
| E08 | [`gate_error_audit/`](../artifacts/gate_error_audit/) | v3.1 모델별 원출력·manifest·score·사례 감사 |
| E09 | [`qwen35_2b_ptq_v0.1.json`](../artifacts/ptq_runs/qwen35_2b_ptq_v0.1.json) | Qwen revision, llama.cpp commit, 변환 시간과 파일 크기 |
| E10 | [`qwen35_2b_gguf_case_replay_v2_aggregate.json`](../artifacts/ptq_runs/qwen35_2b_gguf_case_replay_v2_aggregate.json) | 유효한 Qwen V2 F16/Q4/Q8 baseline |
| E11 | [`QWEN35_2B_FP16_Q4_Q8_COMPARISON_v0.2.md`](QWEN35_2B_FP16_Q4_Q8_COMPARISON_v0.2.md), [`V3.2 aggregate`](../artifacts/ptq_runs/qwen35_2b_gguf_case_replay_v3_2_aggregate.json) | Qwen V3.2 수치·사례·V2 대비 변화 |
| E12 | [`QAT_PILOT_READINESS_v0.1.md`](QAT_PILOT_READINESS_v0.1.md), [`gemma4_e2b_ptq_v0.1.json`](../artifacts/ptq_runs/gemma4_e2b_ptq_v0.1.json) | Gemma Colab RAM 실패와 QAT 보류 근거 |
| E13 | [`gemma4_e2b_local_ptq_v1.json`](../artifacts/ptq_runs/gemma4_e2b_local_ptq_v1.json) | Gemma 파일 크기·해시·실행 설정 |
| E14 | [`GEMMA4_E2B_BF16_Q4_Q8_COMPARISON_v0.1.md`](GEMMA4_E2B_BF16_Q4_Q8_COMPARISON_v0.1.md), [`Gemma aggregate`](../artifacts/ptq_runs/gemma4_e2b_gguf_case_replay_v1_aggregate.json) | Gemma Q4 회귀, Q8 품질 보존, Qwen 비교 |
| E15 | [`PROMPT_V3_3_COMMON_FAILURE_REMEDIATION_v0.1.md`](PROMPT_V3_3_COMMON_FAILURE_REMEDIATION_v0.1.md), [`v3.3 aggregate`](../artifacts/ptq_runs/gemma4_e2b_bf16_prompt_v3_3_gate_v1_aggregate.json) | 공통 실패 분류, v3.3 개선과 잔여 실패 |
| E16 | [`prompt_v3_2_v3_3_size.json`](../artifacts/gate_error_audit/prompt_v3_2_v3_3_size.json) | v3.2/v3.3 prompt hash·token 수 |
| E17 | [`model_delivery_manifest_20261005.json`](../artifacts/model_delivery_manifest_20261005.json) | Android 전달 모델의 Drive URL·bytes·SHA-256·출처 |
| E18 | [Git 커밋 이력](https://github.com/cjuproject34/Kioguard/commits/main/research/llm-intent/evaluation) | 하네스·prompt·분석 변경의 시간순 추적 |

---

## 23. 최종 판단

현재까지의 작업은 “어떤 작은 모델이 안전한 구조화 의도분류 후보가 될 수 있는지”를 빠르게 좁히는 단계까지 완료했다. 최초 7모델 게이트에서는 안전·계약·의미를 모두 만족하는 모델이 없었고, 오류를 구조·문맥·안전으로 분해하면서 prompt와 실행기를 수정했다. Qwen3.5-2B는 Q4_K_M에서 1.222 GiB의 작은 실측 후보를 만들었고, Gemma 4 E2B는 Q8_0에서 BF16 품질을 보존했다. Gemma Q4는 안전 회귀 때문에 제외했다.

가장 좋은 개발 수치는 Gemma BF16 prompt v3.3의 full exact 75%, Macro F1 0.8810, high-impact 100%, 안전 위반 0건이다. 그러나 같은 20건을 보고 개선한 결과이고 Q8 v3.3·166건·독립 test·Android 측정이 없으므로 제품 정확도 결론은 아니다. 다음 의사결정은 사람 검수된 데이터와 S24 Ultra 실측이 내려야 한다.

