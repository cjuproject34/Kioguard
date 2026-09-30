# microsoft/Phi-3-mini-4k-instruct gate error audit

이 문서는 계약 무효 출력의 내부 의미 오류를 확인하기 위한 진단이다. 기존 strict 점수를 대체하지 않는다.

- 사례: 20
- strict JSON: 0/20
- 정규화 JSON: 20/20
- 계약을 무시한 의도 순서 일치: 11/20
- 위험한 추가 행동: 1건
- must-not 위반: 2건

## 오류 범주

| 범주 | 사례 수 |
|---|---:|
| CONDITION | 3 |
| DANGEROUS_EXTRA | 1 |
| DEPENDENCY | 4 |
| FALLBACK | 3 |
| INTENT | 9 |
| MUST_NOT | 2 |
| REQUEST_COUNT | 3 |
| SLOTS | 20 |
| TARGET | 16 |
| TRANSPORT_WRAPPER | 20 |

## 추가 request 키

| 키 | 사례 수 |
|---|---:|

세부 사례는 `case_error_audit.csv`에서 확인한다.
