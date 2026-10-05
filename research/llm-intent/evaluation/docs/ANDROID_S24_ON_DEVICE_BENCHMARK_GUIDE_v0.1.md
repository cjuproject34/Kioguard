# Galaxy S24 Ultra 온디바이스 실측 절차 v0.1

작성일: 2026-10-05  
대상 독자: Android 실측을 담당하는 팀원  
목적: 완성 앱을 만들기 전에 Galaxy S24 Ultra에서 KioGuard GGUF 후보의 로드 가능 여부, 속도, 메모리, 안정성, 발열과 실제 20건 출력을 같은 조건으로 측정한다.

## 1. 이번 작업의 범위

1차 실측에는 완성된 KioGuard 앱이 필요하지 않다. Windows PC에서 Android NDK로 `llama.cpp`의 `llama-bench`와 추론 실행 파일을 `arm64-v8a`용으로 빌드하고, ADB로 휴대폰에 전송해 실행한다.

이 단계에서 확인할 항목은 다음과 같다.

- 모델 파일이 실제 휴대폰에서 로드되는가
- 프롬프트 처리와 토큰 생성 속도는 얼마인가
- 실제 prompt v3.3 요청의 종단 간 지연 시간은 얼마인가
- 프로세스 메모리와 연속 실행 중 발열은 어느 정도인가
- PC/Colab과 같은 JSON 계약을 생성하는가
- 실행 중 OOM, 프로세스 종료 또는 심한 성능 저하가 발생하는가

최종 후보가 좁혀지면 `llama.cpp/examples/llama.android` 기반 최소 APK에서 앱 시작, 백그라운드 복귀, 모델 재사용, Android Studio Profiler 측정을 추가한다. 이 2차 작업은 1차 CLI 실측 결과에 포함하지 않는다.

## 2. 기준 단말과 후보

| 항목 | 기준 |
|---|---|
| 단말 | Galaxy S24 Ultra |
| SoC | Snapdragon 8 Gen 3 |
| RAM | 12GB |
| OS | Android 16 / One UI 8.5 |
| 여유 저장공간 | 약 170GB, 실행 전에 다시 기록 |
| 1순위 경량 후보 | Qwen3.5-2B Q4_K_M, 1.222 GiB |
| 1순위 품질 후보 | Gemma 4 E2B Q8_0, 4.626 GiB |
| 기준 prompt | `prompts/prompt_v3_3_full.txt` |
| 생성 설정 | temperature 0, seed 20260930, 최대 220토큰 |

Gemma Q8_0은 prompt v3.2 20건에서 BF16과 같은 집계 품질을 보였고, Qwen Q4_K_M은 현재 가장 작은 실기 후보이다. Android 실측은 품질 평가를 대체하지 않으며, 두 후보의 최종 채택을 뜻하지 않는다.

## 3. 담당자가 제출할 산출물

다음 파일을 한 실행 묶음으로 제출한다. `<run-id>`는 `YYYYMMDD-s24u-cpu-v1` 형식을 권장한다.

```text
android_benchmark/<run-id>/
├── device_info.txt
├── adb_devices.txt
├── runtime_manifest.json
├── model_hashes.txt
├── qwen_q4_bench.json
├── gemma_q8_bench.json
├── qwen_q4_cases.jsonl
├── gemma_q8_cases.jsonl
├── qwen_q4_meminfo.txt
├── gemma_q8_meminfo.txt
├── thermal_before.txt
├── thermal_after_qwen.txt
├── thermal_after_gemma.txt
└── summary.md
```

GGUF 모델, Android SDK, NDK, 실행 바이너리와 대용량 원시 로그는 Git에 커밋하지 않는다. 최종 검토 후 요약과 작은 JSON/JSONL만 `evaluation/artifacts/android_benchmark/<run-id>/`에 추가한다.

## 4. PC 사전 준비

### 4.1 필수 설치

1. [Android Studio 안정 버전](https://developer.android.com/studio/install)
2. Android Studio의 `Tools > SDK Manager > SDK Tools`에서 다음 항목
   - Android SDK Platform-Tools
   - Android SDK Command-line Tools (latest)
   - Android SDK Build-Tools
   - NDK (Side by side)
   - CMake
   - LLDB
3. Git for Windows
4. ADB가 단말을 찾지 못할 때만 [Samsung USB Driver](https://developer.android.com/studio/run/oem-usb)

Android Emulator, CUDA, Docker, Visual Studio 전체 패키지와 별도 JDK는 필요하지 않다. Android NDK와 CMake 설치 절차는 [Android 공식 문서](https://developer.android.com/studio/projects/install-ndk)를 따른다.

### 4.2 설치 확인

PowerShell에서 다음을 확인한다.

```powershell
adb version
git --version
```

`adb`가 PATH에 없다면 기본 설치 위치의 Platform-Tools를 현재 세션 PATH에 추가한다.

```powershell
$AndroidSdk = Join-Path $env:LOCALAPPDATA "Android\Sdk"
$env:Path = "$AndroidSdk\platform-tools;$env:Path"
adb version
```

## 5. 휴대폰 연결

1. `설정 > 휴대전화 정보 > 소프트웨어 정보`에서 빌드번호를 7회 누른다.
2. `개발자 옵션 > USB 디버깅`을 활성화한다.
3. 데이터 전송이 가능한 USB 케이블로 PC와 연결한다.
4. 휴대폰에 나타나는 RSA 디버깅 허용 창을 승인한다.
5. 다음 명령으로 연결을 확인한다.

```powershell
adb kill-server
adb start-server
adb devices -l
```

상태가 `device`이면 정상이다. `unauthorized`이면 휴대폰 화면에서 승인을 완료한다. 목록이 비어 있으면 케이블, USB 모드와 Samsung USB Driver를 확인한다. ADB 사용법은 [Android 공식 ADB 문서](https://developer.android.com/tools/adb)를 따른다.

## 6. 측정 환경 기록

실행마다 결과 폴더를 새로 만든다.

```powershell
$RunId = "20261005-s24u-cpu-v1"
$ResultDir = Join-Path $PWD "android_benchmark\$RunId"
New-Item -ItemType Directory -Force $ResultDir | Out-Null

adb devices -l | Set-Content -Encoding utf8 "$ResultDir\adb_devices.txt"
adb shell getprop | Set-Content -Encoding utf8 "$ResultDir\device_info.txt"
adb shell dumpsys battery | Add-Content -Encoding utf8 "$ResultDir\device_info.txt"
adb shell df -h /data | Add-Content -Encoding utf8 "$ResultDir\device_info.txt"
adb shell dumpsys thermalservice | Set-Content -Encoding utf8 "$ResultDir\thermal_before.txt"
```

비교 조건을 일정하게 유지한다.

- 휴대폰을 재부팅하고 불필요한 앱을 종료한다.
- 화면 밝기, 배터리 상태, 충전 여부와 실내 온도를 기록한다.
- 각 모델 측정 전 단말을 충분히 식힌다.
- 첫 실행은 process-cold, 이후 반복은 warm 연산으로 구분한다.
- 루팅하지 않은 Android에서는 OS 파일 캐시를 완전히 비울 수 없으므로 `cold`를 완전한 저장장치 cold cache라고 표현하지 않는다.
- 모델 순서에 따른 발열 편향을 줄이기 위해 가능하면 A/B와 B/A 순서를 각각 한 번 수행한다.

## 7. Android용 llama.cpp 빌드

### 7.1 runtime revision 원칙

기존 실험은 Qwen에 `b04642061d183dff8504127dfbee1c1a8352682c`, Gemma에 `7fe450e19`를 사용했다. Android의 두 모델 비교에서는 엔진 차이를 제거하기 위해 **같은 llama.cpp commit**을 사용한다. 시작 기준은 Gemma 4를 지원하는 `7fe450e19`이다.

Qwen이 이 commit에서 로드되지 않으면 임의로 revision을 바꾸지 말고 오류 로그를 남긴다. 이후 두 모델을 모두 지원하는 하나의 commit을 지정해 전체 측정을 처음부터 다시 수행한다.

### 7.2 SDK 도구 경로 선택

```powershell
$AndroidSdk = Join-Path $env:LOCALAPPDATA "Android\Sdk"
$NdkDir = Get-ChildItem "$AndroidSdk\ndk" -Directory |
  Sort-Object { [version]$_.Name } -Descending |
  Select-Object -First 1 -ExpandProperty FullName
$CmakeDir = Get-ChildItem "$AndroidSdk\cmake" -Directory |
  Sort-Object { [version]$_.Name } -Descending |
  Select-Object -First 1 -ExpandProperty FullName
$Cmake = Join-Path $CmakeDir "bin\cmake.exe"
$Ninja = Join-Path $CmakeDir "bin\ninja.exe"

$NdkDir
$Cmake
$Ninja
```

세 경로가 모두 존재해야 한다. 팀 결과에는 선택된 NDK와 CMake 버전을 기록한다.

### 7.3 소스와 빌드

```powershell
$WorkRoot = "C:\KioGuard\android-bench"
$LlamaRoot = Join-Path $WorkRoot "llama.cpp"
$BuildDir = Join-Path $LlamaRoot "build-android-arm64"
$PackageDir = Join-Path $LlamaRoot "package-android-arm64"

New-Item -ItemType Directory -Force $WorkRoot | Out-Null
git clone https://github.com/ggml-org/llama.cpp.git $LlamaRoot
git -C $LlamaRoot checkout --detach 7fe450e19

& $Cmake -S $LlamaRoot -B $BuildDir -G Ninja `
  "-DCMAKE_TOOLCHAIN_FILE=$NdkDir\build\cmake\android.toolchain.cmake" `
  "-DCMAKE_MAKE_PROGRAM=$Ninja" `
  -DANDROID_ABI=arm64-v8a `
  -DANDROID_PLATFORM=android-28 `
  -DCMAKE_BUILD_TYPE=Release `
  -DGGML_NATIVE=OFF `
  -DGGML_BACKEND_DL=ON `
  -DGGML_CPU_ALL_VARIANTS=ON `
  -DGGML_OPENMP=OFF `
  -DLLAMA_CURL=OFF

& $Cmake --build $BuildDir --config Release -j 8
& $Cmake --install $BuildDir --prefix $PackageDir
```

`arm64-v8a`, `GGML_NATIVE=OFF`, Android toolchain과 CPU variant 빌드는 [llama.cpp의 공식 Android CI 설정](https://github.com/ggml-org/llama.cpp/blob/master/.github/workflows/build-android.yml)을 기준으로 한다.

빌드 후 다음 파일을 찾는다. commit에 따라 설치 경로가 조금 다를 수 있다.

```powershell
Get-ChildItem $PackageDir -Recurse -File |
  Where-Object Name -Match "llama-bench|llama-cli|llama-completion|\.so$" |
  Select-Object FullName
```

필수 도구는 `llama-bench`와 실제 생성에 사용할 `llama-cli` 또는 `llama-completion`이다. 실행 파일이나 `.so`가 없으면 `cmake --build` 오류를 먼저 해결하고 진행한다.

## 8. 모델 수령과 동일성 확인

모델은 프로젝트 담당자에게 별도 파일 전송 경로로 받는다. GitHub에 모델을 올리지 않는다.

| 후보 | 예상 파일명 | 바이트 | SHA-256 |
|---|---|---:|---|
| Qwen3.5-2B Q4_K_M | `qwen35-2b-q4_k_m.gguf` | 1,312,164,768 | 수령 후 계산하여 기존 생성자 기록과 대조 |
| Gemma 4 E2B Q8_0 | `gemma-4-E2B-it-q8_0.gguf` | 4,967,497,152 | `4b9e6317389d66a2a8d6fb4a6fd1dda89915906752a8e3807a1c4014dd3133b4` |

```powershell
$QwenModel = "D:\KioGuard\models\qwen35-2b-q4_k_m.gguf"
$GemmaModel = "D:\KioGuard\models\gemma-4-E2B-it-q8_0.gguf"

Get-FileHash $QwenModel -Algorithm SHA256 |
  Format-List | Out-String | Set-Content -Encoding utf8 "$ResultDir\model_hashes.txt"
Get-FileHash $GemmaModel -Algorithm SHA256 |
  Format-List | Out-String | Add-Content -Encoding utf8 "$ResultDir\model_hashes.txt"
```

파일 크기나 해시가 다르면 측정을 시작하지 않는다. Qwen의 승인 해시는 생성자와 대조해 `model_hashes.txt`에 함께 기록한다.

## 9. 실행 파일과 모델 전송

```powershell
$RemoteRoot = "/data/local/tmp/kioguard"
adb shell "mkdir -p $RemoteRoot/runtime $RemoteRoot/models $RemoteRoot/results"
adb push "$PackageDir\." "$RemoteRoot/runtime/"
adb push $QwenModel "$RemoteRoot/models/qwen35-2b-q4_k_m.gguf"
adb push $GemmaModel "$RemoteRoot/models/gemma-4-E2B-it-q8_0.gguf"
adb shell "find $RemoteRoot/runtime -type f -path '*/bin/*' -exec chmod 755 {} \;"
adb shell "ls -lh $RemoteRoot/models"
```

4.6GB 모델 전송은 시간이 걸릴 수 있다. 전송이 끊기면 휴대폰과 PC의 파일 크기를 다시 비교한다.

설치 구조를 확인해 실제 원격 경로를 환경 변수로 정한다.

```powershell
adb shell "find $RemoteRoot/runtime -type f -name 'llama-bench*' -o -name 'llama-completion*' -o -name 'llama-cli*'"
adb shell "find $RemoteRoot/runtime -type f -name '*.so'"
```

아래 예시에서는 실행 파일이 `$RemoteRoot/runtime/bin`, 라이브러리가 `$RemoteRoot/runtime/lib`에 있다고 가정한다. 실제 설치 결과가 다르면 경로만 수정하고 기록한다.

## 10. 사전 점검

```powershell
adb shell "export LD_LIBRARY_PATH=$RemoteRoot/runtime/lib; $RemoteRoot/runtime/bin/llama-bench --help" |
  Set-Content -Encoding utf8 "$ResultDir\llama_bench_help.txt"
adb shell "export LD_LIBRARY_PATH=$RemoteRoot/runtime/lib; $RemoteRoot/runtime/bin/llama-bench --list-devices" |
  Set-Content -Encoding utf8 "$ResultDir\llama_devices.txt"
```

그다음 각 모델을 1회만 로드한다. 첫 시도는 CPU 고정(`-ngl 0`)으로 한다.

```powershell
adb shell "export LD_LIBRARY_PATH=$RemoteRoot/runtime/lib; $RemoteRoot/runtime/bin/llama-bench -m $RemoteRoot/models/qwen35-2b-q4_k_m.gguf -p 32 -n 8 -t 4 -ngl 0 -r 1"
adb shell "export LD_LIBRARY_PATH=$RemoteRoot/runtime/lib; $RemoteRoot/runtime/bin/llama-bench -m $RemoteRoot/models/gemma-4-E2B-it-q8_0.gguf -p 32 -n 8 -t 4 -ngl 0 -r 1"
```

두 모델 중 하나라도 로드 실패하면 전체 벤치마크로 넘어가지 않는다. 전체 stderr, 종료 코드, runtime commit과 모델 해시를 보존한다.

## 11. llama-bench 성능 측정

`llama-bench`는 프롬프트 처리와 텍스트 생성 속도를 반복 측정한다. 토큰화와 sampling 시간은 포함하지 않으므로, 이 결과를 사용자 종단 간 지연 시간으로 사용하지 않는다. 옵션과 출력 정의는 [공식 llama-bench 문서](https://github.com/ggml-org/llama.cpp/blob/master/tools/llama-bench/README.md)를 따른다.

### 11.1 짧은 공통 기준

```powershell
$QwenBench = "export LD_LIBRARY_PATH=$RemoteRoot/runtime/lib; $RemoteRoot/runtime/bin/llama-bench -m $RemoteRoot/models/qwen35-2b-q4_k_m.gguf -p 512 -n 64 -t 4,8 -ngl 0 -r 5 -o json"
$GemmaBench = "export LD_LIBRARY_PATH=$RemoteRoot/runtime/lib; $RemoteRoot/runtime/bin/llama-bench -m $RemoteRoot/models/gemma-4-E2B-it-q8_0.gguf -p 512 -n 64 -t 4,8 -ngl 0 -r 5 -o json"

adb shell $QwenBench | Set-Content -Encoding utf8 "$ResultDir\qwen_q4_bench.json"
adb shell $GemmaBench | Set-Content -Encoding utf8 "$ResultDir\gemma_q8_bench.json"
```

### 11.2 실제 prompt 길이 근접 기준

prompt v3.3은 Gemma 토크나이저 기준 약 3,027토큰이다. 짧은 기준이 끝난 뒤 선택된 스레드 수로 prompt processing 3,072토큰과 생성 220토큰을 각각 측정한다.

```powershell
$Threads = 8
adb shell "export LD_LIBRARY_PATH=$RemoteRoot/runtime/lib; $RemoteRoot/runtime/bin/llama-bench -m $RemoteRoot/models/qwen35-2b-q4_k_m.gguf -p 3072 -n 220 -t $Threads -ngl 0 -r 5 -o json" |
  Set-Content -Encoding utf8 "$ResultDir\qwen_q4_bench_long.json"
adb shell "export LD_LIBRARY_PATH=$RemoteRoot/runtime/lib; $RemoteRoot/runtime/bin/llama-bench -m $RemoteRoot/models/gemma-4-E2B-it-q8_0.gguf -p 3072 -n 220 -t $Threads -ngl 0 -r 5 -o json" |
  Set-Content -Encoding utf8 "$ResultDir\gemma_q8_bench_long.json"
```

실제 모델별 토큰 수는 다를 수 있으므로 3,072는 성능 비교용 근사치로 표시한다.

## 12. 실제 KioGuard 20건 종단 간 측정

성능 도구 결과와 별도로 실제 prompt, 토큰화, sampling, JSON 생성을 포함한 20건을 실행한다.

### 12.1 입력과 렌더링

- 평가 입력: `artifacts/gate_error_audit/qwen35_2b_v3_1/gate_gold.jsonl`
- prompt: `prompts/prompt_v3_3_full.txt`
- Gemma 렌더링 기준: `scripts/run_gemma4_e2b_gguf_case_replay.py`의 `load_cases_and_prompts`
- Qwen 렌더링 기준: `scripts/run_qwen35_2b_gguf_case_replay.py`의 `render_qwen35_user_prompt`

PC 측 실행 하네스는 각 사례에 대해 다음 순서를 수행해야 한다.

1. 저장소의 prompt와 `context`, `utterance`를 합친다.
2. 모델별 native chat template를 기존 실행기와 동일하게 렌더링한다.
3. UTF-8 prompt 파일을 휴대폰에 전송한다.
4. Android 추론 실행 파일을 새 프로세스로 시작한다.
5. host wall time, exit code, stdout, stderr를 저장한다.
6. stdout에서 전송 wrapper만 정규화하고 모델 의미 출력은 수정하지 않는다.
7. `case_id`, `raw_output`, `normalized_output`, `generation_seconds`, `status`를 JSONL에 기록한다.
8. 20건 완료 후 저장소의 `score_predictions.py`, `score_predictions_v2.py`, `audit_gate_errors.py`로 PC에서 채점한다.

추론 인수는 기존 실행기와 맞춘다.

| 인수 | 값 |
|---|---:|
| temperature | 0 |
| seed | 20260930 |
| max new tokens | 220 |
| GPU layers | 0 |
| Gemma context | 4096 |
| Qwen context | 8192 |
| 스레드 | `llama-bench` 결과로 선택하고 manifest에 기록 |

Android build에서 지원하는 인수는 먼저 `--help`로 확인한다. 인수 이름이 달라졌다면 동등한 설정을 사용하고 변경 사항을 `runtime_manifest.json`에 기록한다. Qwen과 Gemma의 chat template를 서로 바꾸어 사용하지 않는다.

이번 20건은 이미 prompt 개선에 사용한 개발 gate이므로 Android 실행 일치와 회귀 확인용이다. 독립 정확도라고 보고하지 않는다.

## 13. 메모리와 발열 측정

CLI 프로세스를 백그라운드로 실행한 상태에서 PID를 얻어 다음 값을 1초 간격으로 수집한다.

```sh
PID=$(pidof llama-completion)
cat /proc/$PID/status | grep -E 'VmRSS|VmHWM|VmSize'
dumpsys meminfo $PID
```

단일 snapshot은 peak를 놓칠 수 있으므로 최소 1초 간격 반복값 중 최대치를 사용한다. 기록할 값은 다음과 같다.

- peak RSS 또는 VmHWM
- PSS total
- 모델 로드 후 추론 전 메모리
- 생성 중 최대 메모리
- 프로세스 종료 또는 LMK 발생 여부

각 모델 연속 실행 직후 발열과 배터리 상태를 저장한다.

```powershell
adb shell dumpsys thermalservice | Set-Content -Encoding utf8 "$ResultDir\thermal_after_qwen.txt"
adb shell dumpsys battery | Set-Content -Encoding utf8 "$ResultDir\battery_after_qwen.txt"

adb shell dumpsys thermalservice | Set-Content -Encoding utf8 "$ResultDir\thermal_after_gemma.txt"
adb shell dumpsys battery | Set-Content -Encoding utf8 "$ResultDir\battery_after_gemma.txt"
```

센서 이름과 단위는 단말/OS에 따라 다를 수 있다. 가장 높은 온도 숫자만 임의 선택하지 말고 원문과 사용한 센서를 함께 보존한다.

## 14. 결과 요약 기준

`summary.md`에는 다음 표를 작성한다.

| 지표 | Qwen Q4_K_M | Gemma Q8_0 |
|---|---:|---:|
| 모델 크기 | | |
| 로드 성공 | | |
| process-cold 첫 실행 | | |
| prompt processing 512 t/s | | |
| prompt processing 3072 t/s | | |
| generation 64 t/s | | |
| generation 220 t/s | | |
| 실제 20건 성공 수 | | |
| 실제 지연 p50 | | |
| 실제 지연 p95 | | |
| peak RSS/PSS | | |
| 계약 유효율 | | |
| full exact | | |
| Macro intent F1 | | |
| 위험 행동 / must-not | | |
| 연속 실행 전후 온도 | | |
| OOM/비정상 종료 | | |

p50/p95는 정렬된 실제 20건 wall time으로 계산한다. 평균만 보고하지 않는다. 첫 실행은 별도 열에 두고 반복값과 섞지 않는다.

## 15. 완료 조건과 중단 조건

다음을 모두 만족하면 1차 실측 완료이다.

- 두 모델에 동일한 Android runtime commit을 사용했다.
- 모델 크기와 SHA-256을 기록했다.
- CPU 기준 `llama-bench`가 각 모델에서 5회 이상 완료됐다.
- 실제 prompt v3.3 20건의 원출력, 지연 시간과 채점 결과를 보존했다.
- 메모리, 배터리와 thermalservice 원문을 보존했다.
- p50/p95와 실패 사례를 `summary.md`에 기록했다.
- Android 측정값을 PC/Colab 생성 시간과 혼합하지 않았다.

다음 상황에서는 비교를 중단하고 원인을 먼저 보고한다.

- 모델 해시 또는 파일 크기가 기준과 다름
- 두 모델의 llama.cpp commit이 다름
- 모델 로드 실패 또는 Android가 프로세스를 종료함
- chat template 또는 reasoning 설정이 기존 실행기와 다름
- 동일 조건 반복 중 결과 JSON 구조가 일관되지 않음
- 측정 중 단말 온도가 계속 상승하여 명확한 스로틀링이 발생함

## 16. 2차 최소 APK 측정

1차 실측 후 선택한 1~2개 후보만 [공식 `llama.android` 예제](https://github.com/ggml-org/llama.cpp/tree/master/examples/llama.android)에 연결한다. 최소 APK에는 모델 선택, 20건 실행, 결과 내보내기 기능만 넣는다.

이 단계에서 추가 측정할 항목은 다음과 같다.

- 앱 최초 시작과 모델 초기화 시간
- 같은 프로세스에서 모델을 유지한 warm 추론
- 백그라운드 이동과 복귀 후 모델 유지 여부
- Android Studio Profiler의 Java/native 메모리
- 앱 저장공간과 모델 배포 방식
- 장시간 반복 시 ANR, crash와 thermal throttling

최소 APK 결과가 CLI 결과와 크게 다르면 앱 lifecycle, JNI 복사, 모델 파일 접근 방식과 context 재사용을 분리해 조사한다.

## 17. 참고 자료

- [llama.cpp Android 예제](https://github.com/ggml-org/llama.cpp/tree/master/examples/llama.android)
- [llama.cpp Android CI 빌드](https://github.com/ggml-org/llama.cpp/blob/master/.github/workflows/build-android.yml)
- [llama-bench 사용법](https://github.com/ggml-org/llama.cpp/blob/master/tools/llama-bench/README.md)
- [Android Studio 설치](https://developer.android.com/studio/install)
- [Android NDK와 CMake 설치](https://developer.android.com/studio/projects/install-ndk)
- [Android Debug Bridge](https://developer.android.com/tools/adb)
- `GEMMA4_E2B_BF16_Q4_Q8_COMPARISON_v0.1.md`
- `QWEN35_2B_FP16_Q4_Q8_COMPARISON_v0.2.md`
- `PROMPT_V3_3_COMMON_FAILURE_REMEDIATION_v0.1.md`

