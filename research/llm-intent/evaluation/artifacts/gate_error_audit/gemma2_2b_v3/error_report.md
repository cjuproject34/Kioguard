# google/gemma-2-2b-it gate error audit

이 문서는 계약 무효 출력의 내부 의미 오류를 확인하기 위한 진단이다. 기존 strict 점수를 대체하지 않는다.

- 사례: 20
- strict JSON: 0/20
- 정규화 JSON: 20/20
- 계약을 무시한 의도 순서 일치: 3/20
- 위험한 추가 행동: 5건
- must-not 위반: 4건

## 오류 범주

| 범주 | 사례 수 |
|---|---:|
| CONDITION | 16 |
| DANGEROUS_EXTRA | 5 |
| DEPENDENCY | 17 |
| FALLBACK | 3 |
| INTENT | 17 |
| MUST_NOT | 4 |
| REQUEST_CONTRACT | 20 |
| REQUEST_COUNT | 16 |
| SLOTS | 19 |
| TARGET | 17 |
| TOP_LEVEL_CONTRACT | 3 |
| TRANSPORT_WRAPPER | 20 |

## 추가 request 키

| 키 | 사례 수 |
|---|---:|
| `fallback` | 20 |

세부 사례는 `case_error_audit.csv`에서 확인한다.
