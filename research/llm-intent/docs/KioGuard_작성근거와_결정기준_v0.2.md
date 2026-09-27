# KioGuard 상세 명세서 작성 근거와 결정 기준

작성일: 2026-09-27 · 대상: [상세 명세서 v0.2](KioGuard_상세명세서_v0.2.md)

## 1. 이번 작업에서 확인한 범위

로컬 엑셀·개발보고서 PDF·5차 회의록 DOCX를 다시 읽어 추출한 텍스트를 확인했다. 연결된 Drive의 정답 CSV·학습 CSV·통합 Colab 노트북을 다시 읽었다. 상세 양자화·Rule·파서 판단은 같은 대화에서 수행한 [Colab 감사보고서](KioGuard_기존_Colab_실험_검토보고서.md)와 저장된 검산 자료를 재사용했다. 공식 모델 카드·엔진·Android 문서는 작성일에 웹에서 확인했다.

이번에 새로 수행한 것은 문서·데이터 검토, 48발화의 조건부 수정안 작성, 명세서 작성과 산출물 구조 검증이다. 모델을 실행하거나 Android 기기를 조작하지 않았다. 구현 코드와 원본 문서를 변경하지 않았다. 따라서 실제 성능·모델 배포 성공·QAT 효과는 새로 확인한 사실이 아니다.

## 2. 자료를 적용한 우선순위

1. 사용자가 대화에서 명시한 최신 목표·정정: 모든 AI 추론 온디바이스, 선택적 LLM/Rule, S24 Ultra 보유 시험 기기, 기존 성능 실험은 Colab에서만 수행, 작업 전 확인.
2. 현재 읽을 수 있는 코드·저장 출력·CSV: 실제 모델 ID, 데이터 수, 관측 결과의 확인 범위.
3. 엑셀·개발보고서: 제품 의도·기능 범위와 과거 보고값. 수치가 원출력과 충돌하면 보고값과 확인값을 분리.
4. 회의록과 직접 메모: 문제의식과 검토 과제. 수행 완료·하드웨어 수치·서버 구조를 자동으로 현재 사실이나 작업 지시로 적용하지 않음.
5. 공급자 공식 문서: 공개 모델·API·변환 경로의 존재와 제약. KioGuard의 한국어 의도분류 정확도·모바일 지연의 증거로 대체하지 않음.

첨부 자료의 “QAT 필수”, “기성 양자화본 사용 금지”, “서버/A2A” 같은 서술은 자료 속 과거 지침으로 다뤘다. 현재 사용자의 합의에 맞춰 직접 PTQ 비교를 기본 연구로 제안하고 QAT는 조건부로 정의했으며, 서버 AI 추론을 제품 범위에 추가하지 않았다.

## 3. 프로젝트 자료와 설계의 연결

| 자료 | 확인한 내용 | 명세에 반영한 결정 |
|---|---|---|
| 로컬 `LLM 의도분석 온디바이스.xlsx`의 의도정의 B4:D11 | 주문·옵션·매장/포장·결제·혜택·취소/처음으로·도움·정보의 8범주 | 주제와 요청 종류를 분리하는 V2 정의 |
| 같은 파일 정답라벨 시트 | 질문과 선택, 영수증과 결제수단, 접근성과 도움, 뒤로와 초기화가 섞임 | INFO/GUIDE/RECEIPT/APP_CONTROL/BACK/CANCEL/RESET 경계 분리 |
| 개발보고서 2~3쪽 | 개인 단말, 카페·관공서, STT/OCR/LLM/TTS 로컬 처리, 화면 버튼 안내 | 개인 스마트폰 안내 보조 앱, 외부 키오스크 자동 조작 제외 |
| 개발보고서 6~7쪽 | UI·오케스트레이션·엔진, 음성 안내, OCR 좌표·유연 매칭·화면 추적 | F01~F14 및 S00~S08. 글자 영역·실제 버튼 영역을 구분 |
| 개발보고서 4·7쪽의 97.9%·무손실 표현 | 기존 성과로 보고돼 있으나 감사에서 근거 범위 축소 | 새 명세의 달성값으로 승계하지 않음 |
| 5차 회의록과 사용자의 직접 메모 | 의도분류, 오류 Fallback, 양자화 보정, RAM·발열 측정 요구 | 공통 Validator, 오류 상태 분리, 통제 PTQ/QAT, 실기기 장시간 시험 |
| [정답 CSV](https://drive.google.com/file/d/1N10Qfh3NN_WVdxdqVGXyw1ePFQ08kcLz/view) | 48행·고유 문자열 38개, 실제 화면 문맥 없음 | 원본 보존·조건부 라벨링·중복 그룹 관리 |
| [학습 CSV](https://drive.google.com/file/d/1Fna6PuRV6jEDqoBxBTQs1_SclbDAaswA/view) | 현재 126행. 파일명 QAT만으로 학습 수행 입증 불가 | 247개·QAT 완료 주장을 승계하지 않음 |
| [통합 노트북](https://colab.research.google.com/drive/1ayw4qiTgsnCMaWkqjnNGD3FJr9y9DwFo) 셀 10/14~18/20 | Gemma GGUF, ggml-small-ko-q5_0.bin, MMS Korean TTS, 단계별 함수 호출 | STT 원본 출처 확인·TTS 보고/코드 불일치 표시·실제 Android artifact 확인 작업 |
| Colab 감사보고서 | Rule 45/48, 저장 Q4 41/48, 재구성 Hybrid 47/48, 최종 f16 37/48, parser와 template 차이 | 고정된 평가 계약·원출력 보존·동일 조건 비교·baseline 보존 |

원본 파일명이 “2026 한이음 드림업 개발보고서_KioGuard.pdf”이고 본문 작성일이 2026-09-08임을 확인했다. 사용자 메시지의 “20205” 표기는 별도 연도의 문서로 해석하지 않았다.

## 4. 의도·우선순위 기준을 이렇게 정한 이유

### 4.1 기존 8개를 그대로 고/저로 나누지 않은 이유

같은 결제 주제라도 수단 선택, 지원 여부 질문, 영수증 요청, 최종 진행 요청이 다르다. 반대로 같은 GUIDE라도 일반 버튼 안내와 PIN 입력 위치 안내의 영향이 다르다. 따라서 의도와 topic을 분리하고, 화면 상태에 따라 영향도를 기록했다.

14개 의도는 완성된 최적 라벨 수가 아니라 기존 경계 문제를 빠짐없이 다루기 위한 초안이다. 라벨 수 증가로 데이터 수집과 혼동 관리 비용이 늘어난다. G0에서 2인 검수로 불필요한 분리를 조정한 뒤 확정한다. 변경된 라벨 체계의 정확도를 과거 8라벨 정확도와 직접 비교하지 않는다.

### 4.2 영향도와 복잡도를 합산하지 않은 이유

잘못된 안내가 금전·개인정보·상태 손실에 미치는 영향은 문장이 짧다는 이유로 작아지지 않는다. H/M/L/U와 C1/C2/C3/CU를 독립 기록하고 H를 우선 적용했다. 고우선순위는 신중한 해석·검증이 필요하다는 뜻이며 긴급한 제어 명령의 실행 순서와 다르다.

### 4.3 연산량을 발화의 정답 라벨로 두지 않은 이유

연산량은 모델·입력 토큰·출력·backend·캐시·재시도에 따라 달라진다. 사전에 “연산량 높음”을 발화만으로 확정하면 실제 측정과 어긋날 수 있다. Router 입력에는 해석 복잡도와 상태 조건을 사용하고, 결과에는 요청당 토큰·지연·메모리·가능한 전력을 기록한다.

### 4.4 Rule 허용 범위를 좁게 잡은 이유

기존 검산에서 “취소하지 마세요”, “생일 카드 문구 알려줘” 같은 반례를 단순 키워드가 승인했다. 전체 패턴·상태·필수 슬롯·부정 부재가 모두 충족되는 L/C1만 직접 처리하도록 했다. 초기 호출률이 높아질 수 있으나, 기존 4%를 새 목표로 강제하는 것보다 잘못된 Rule 승인을 측정·수정하기 쉽다.

### 4.5 재질문을 별도로 둔 이유

LLM이 복잡한 문장을 해석할 수 있어도 없는 화면·선택 대상을 만들어낼 수는 없다. “그걸로”의 대상이 없거나 “민원서류”의 종류가 없으면 의미 분류와 실제 안내 가능 상태를 구분해야 한다. 범위 밖 질문, 입력 오류, 엔진 오류도 다른 결과로 기록한다.

## 5. 기술 선택의 공식 근거

| 근거 ID | 확인한 사실·자료 | 사용한 결정·유보 |
|---|---|---|
| W01 | [Gemma 4 E2B 공식 카드](https://huggingface.co/google/gemma-4-E2B-it): 모바일 목적의 소형 계열, effective/embedding 포함 파라미터 구분, thinking 설정 | 신규 주 비교 후보에 포함. E2B를 실제 총 2B·확정 RAM으로 해석하지 않음 |
| W02 | [Qwen 3.5 2B](https://huggingface.co/Qwen/Qwen3.5-2B), [0.8B](https://huggingface.co/Qwen/Qwen3.5-0.8B): 소형 후보와 non-thinking 경로 | 크기별 품질·비용 비교. 이름이 작다는 이유로 우승 모델 선정하지 않음 |
| W03 | [Kanana-2 1.3B](https://huggingface.co/kakaocorp/kanana-2-1.3b-instruct): 온디바이스 지향·custom hybrid attention | 한국어 추가 후보, Android 변환·kernel 지원을 진입 조건으로 둠 |
| W04 | [llama.cpp Android](https://github.com/ggml-org/llama.cpp/blob/master/docs/android.md): Android 앱·NDK 경로 | 기존 경험을 활용하는 기준 엔진. 해당 단말에서의 최신 모델 성공은 미확인 |
| W05 | [LiteRT-LM](https://developers.google.com/edge/litert-lm): Android 배포·하드웨어 가속 경로 | 대안 엔진 후보. GGUF나 Q4_K_M이 그대로 호환된다고 가정하지 않음 |
| W06 | [llama.cpp quantize](https://github.com/ggml-org/llama.cpp/blob/master/tools/quantize/README.md): 고정밀 GGUF에서 PTQ, 재양자화 주의 | 고정밀/Q8/Q4를 같은 원본에서 생성. 구조·parser 변경 효과와 분리 |
| W07 | [PyTorch QAT](https://pytorch.org/blog/quantization-aware-training-in-torchao-ii/): 학습 중 quantization 모사, 실제 배포 scheme 일치 필요, QLoRA와 구별 | 배포 호환성·실제 PTQ 손실을 QAT 진입 조건으로 둠 |
| W08 | [ML Kit OCR Android](https://developers.google.com/ml-kit/vision/text-recognition/v2/android): 한국어 모델의 bundled/unbundled 선택 | 설치 후 오프라인 준비를 명확히 하기 위해 bundled 우선 |
| W09 | [Android SpeechRecognizer](https://developer.android.com/reference/android/speech/SpeechRecognizer): 일반 서비스와 on-device 경로 구분 | 기본 음성 API를 쓴다는 이유로 온디바이스라고 주장하지 않음 |
| W10 | [Android TTS Voice](https://developer.android.com/reference/android/speech/tts/Voice#isNetworkConnectionRequired()) | 설치된 한국어 voice의 network 요구 여부·오프라인 실동작 확인 |
| W11 | [Android 접근성](https://developer.android.com/guide/topics/ui/accessibility/views/apps-views): 최소 48dp 터치 영역 권고 | UI 최소 조작 영역에 반영. 20sp·56dp는 프로젝트 제안값 |
| W12 | [Android Thermal](https://developer.android.com/games/optimize/adpf/thermal), [dumpsys](https://developer.android.com/tools/dumpsys) | 열 상태·PSS 측정 방법 선택. 온도 센서 종류·메모리 분모 명시 |
| W13 | [Samsung S24 발표](https://news.samsung.com/global/enter-the-new-era-of-mobile-ai-with-samsung-galaxy-s24-series), [S24 Ultra 사양](https://www.samsung.com/sa_en/business/smartphones/galaxy-s/galaxy-s24-ultra-sm-s928bzkcmea/) | 공식 SoC·Octa-Core로 회의 메모의 하드웨어 추정과 구분. 실제 단말 OS·가용 RAM은 별도 확인 |
| W14 | [MMS Korean](https://huggingface.co/facebook/mms-tts-kor), [whisper.cpp](https://github.com/ggml-org/whisper.cpp) | 과거 TTS 코드의 실제 모델명 확인과 STT 배포 경로 참고. 새 성능 주장 없음 |

이 자료는 후보가 존재하고 사용할 수 있는 경로를 설명한다. 모든 공개 모델을 전수 조사해 세계 최신·최고라고 선정한 것은 아니다. 프로젝트에 적합한 소형 공개 후보를 선별한 비교 계획이다. 공급자 벤치마크 수치를 KioGuard의 목표 달성 근거로 전용하지 않았다.

## 6. 수치 목표의 성격과 근거

| 제안값 | 결정 기준 | 확인 전에는 말할 수 없는 것 |
|---|---|---|
| 의도 정확도 ≥95%, Macro F1 ≥0.93 | 새 라벨 체계의 품질을 검증하기 위한 초기 수용 목표. 소수 의도 성능을 평균에 숨기지 않도록 두 지표 사용 | 어느 후보가 이 값을 달성한다는 주장 |
| 고영향 잘못된 안내 승인 관측 0건 | 손실이 큰 오류는 전체 정확도와 별도 관리 | 실제 위험 0·안전성 100% |
| LLM warm P95≤2초, 전체 음성 응답 P95≤5초 | STT·의도 처리·TTS 시작의 대기시간을 나눈 초기 UX 예산 | 기존 Colab 465ms로 모바일 충족 입증 |
| 자동 처리 8초 deadline, 형식 재시도 최대 1회 | 무한 대기·반복 호출 억제, 복구 선택지 제공 | 모든 입력이 8초 안에 정답 처리된다는 보장 |
| 앱 PSS≤4GiB | OS·다른 앱·다른 AI 축을 고려해 시작할 보수적 자원 예산 | S24 Ultra에 반드시 4GiB까지 안전하게 할당 가능하다는 주장 |
| 30분 연속 시험, P95 악화≤20% | 열·누적 상태·메모리 영향의 초기 검증 | 장시간 모든 환경에서 안정적이라는 일반화 |
| 최종 test 720건, 고영향≥200건 | 의도별 최소 사례와 예외 상태를 분리한 초기 연구 규모 | 충분한 통계 검정력이 이미 확보됐다는 주장 |
| 48dp | Android 공식 접근성 권고 | 이 치수 하나로 노년층 사용성·법적 접근성 전체 충족 |

기준값은 외부 논문이 정해 준 절대값이 아니다. 과업 중요도·측정 가능성·사용자 대기 경험을 반영한 제안이다. G1의 예비 측정과 대상 사용자 pilot을 보고 최종 test 전에 동결하며, 변경 시 사용자의 확인과 변경 이유를 남긴다. 실패 결과를 확인한 뒤 같은 test에 맞춰 목표를 낮추지 않는다.

200개의 독립 사례에서 오류가 0개인 경우에도 단측 95% 이항 상한은 `1 - 0.05^(1/200)`로 약 1.49%다. 실제 사례가 같은 화면·화자에 묶이면 독립성 가정도 약해지므로 단순한 “0/200”의 의미를 과장하지 않는다.

## 7. 왜 모델·양자화를 지금 최종 확정하지 않았는가

모델 ID, 초기 엔진, 비교할 양자화 방식과 시험 순서는 구체적으로 지정했다. 다만 실행하지 않은 성능을 사실로 만들지 않기 위해 최종 승자는 G4에 두었다. 특히 최신 Gemma E2B는 실제 총 가중치 규모와 모바일 성능을 이름만으로 판단할 수 없고, Kanana는 아키텍처 지원 확인이 필요하다.

최종 선택은 오프라인·호환성 통과 → 중요한 오류 기준 → 분류 품질 → 메모리·P95·연속 사용 안정성 순서로 판단한다. 비슷한 후보는 자원 효율과 구현·유지보수 비용을 비교한다. 정확도가 미달한 후보를 파일 크기가 작다는 이유로 선정하지 않는다. 아무 후보도 통과하지 않으면 미선정으로 보고한다.

## 8. 적용하면서 발생할 비용과 대응

| 비용·애로사항 | 대응 |
|---|---|
| 8개에서 14개 의도로 늘어나 라벨링·혼동이 증가 | G0에서 독립 검수 후 불필요한 분리 조정. V1/V2 점수 분리 |
| Router의 보수적 정책으로 초기 LLM 호출률 상승 | 낮은 호출률을 고정 목표로 삼지 않고 Rule 오류·전체 지연과 함께 평가 |
| 화면 상태 추적·OCR 오류가 의도 정확도와 분리되지 않음 | 텍스트-only NLU, 화면 선택, 음성 통합을 별도 층으로 측정 |
| STT·LLM native 의존성 충돌, 모든 모델 동시 상주 시 메모리 증가 | 버전 고정·어댑터 분리·순차 스케줄·실제 peak 측정 |
| QAT 학습 형식과 모바일 양자화 불일치 | 지원 가능한 end-to-end 경로를 먼저 검증. 미지원이면 별도 연구로 보류 |
| 고령 사용자·실제 화면 수집 비용 | 작은 pilot로 UX·과업을 확인하고 별도 동의 절차로 확장 |

## 9. 다음 실행 전에 필요한 확인

현재 Android 프로젝트와 실제 모델 자산, 보유 단말의 OS·RAM 상태, 실제 과업 화면을 확인해야 구현과 실측 계획을 확정할 수 있다. 담당자 이름·팀 인원·일정도 제공되지 않아 역할만 배정했다. 명세 작성 승인은 이 자료의 무제한 수집이나 앱 수정·모델 학습의 승인으로 확대하지 않았다.

다음 작업은 (1) 의도·목표·범위에 대한 사용자 검토, (2) 기존 Android 소스와 자산의 읽기 검토, (3) 승인된 범위의 최소 앱 구현·실측으로 나누어 진행한다.
